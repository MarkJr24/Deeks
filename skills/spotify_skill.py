import os
import re
import webbrowser
from typing import Optional, Tuple
from logger import logger
from memory.memory import load_memory

# Scopes needed for playback state inspection and playback control
SPOTIFY_SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-private",
    "user-read-email",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
CACHE_FILE = os.path.join(PROJECT_ROOT, ".spotify_cache")


def _read_env_file() -> dict:
    """Parses key-value pairs from a local .env file if it exists."""
    env_vars = {}
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip('"\'')
        except Exception as e:
            logger.debug(f"Failed to read .env file: {e}")
    return env_vars


def get_spotify_credentials() -> Tuple[Optional[str], Optional[str], str]:
    """
    Loads Spotify API credentials using hierarchical fallback:
    1. System environment variables
    2. Local .env file
    3. Memory store (memory/data.json)
    """
    env_file_data = _read_env_file()

    client_id = (
        os.getenv("SPOTIFY_CLIENT_ID")
        or env_file_data.get("SPOTIFY_CLIENT_ID")
        or load_memory("spotify_client_id")
    )
    client_secret = (
        os.getenv("SPOTIFY_CLIENT_SECRET")
        or env_file_data.get("SPOTIFY_CLIENT_SECRET")
        or load_memory("spotify_client_secret")
    )
    redirect_uri = (
        os.getenv("SPOTIFY_REDIRECT_URI")
        or env_file_data.get("SPOTIFY_REDIRECT_URI")
        or load_memory("spotify_redirect_uri")
        or "http://127.0.0.1:8888/callback"
    )

    # Clean up empty or placeholder strings
    if client_id and "your_spotify_client_id" in client_id:
        client_id = None
    if client_secret and "your_spotify_client_secret" in client_secret:
        client_secret = None

    return client_id, client_secret, redirect_uri


def get_spotify_client():
    """
    Builds and returns an authenticated spotipy.Spotify client using SpotifyOAuth.
    Returns (client, None) on success, or (None, error_message) on failure.
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        logger.error("spotipy library is not installed.")
        return None, "The Spotify integration library is not installed."

    client_id, client_secret, redirect_uri = get_spotify_credentials()

    if not client_id or not client_secret:
        logger.debug("Spotify credentials are missing or unconfigured.")
        return None, "Spotify is not configured yet. Please add your Spotify credentials to the .env file."

    try:
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=" ".join(SPOTIFY_SCOPES),
            cache_path=CACHE_FILE,
            open_browser=True,
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp, None
    except Exception as e:
        logger.exception(f"Failed to initialize Spotify client: {e}")
        return None, "I couldn't connect to Spotify. Please check your credentials."


def get_active_device(sp) -> Optional[dict]:
    """
    Finds the active or available playback device.
    1. Checks sp.current_playback() for an explicitly active device.
    2. Inspects sp.devices() for an active device (is_active == True).
    3. If no device is currently active, falls back to the first available Computer
       device or any available device in sp.devices().
    Returns device dict if found, else None.
    """
    try:
        playback = sp.current_playback()
        if playback and playback.get("device") and playback["device"].get("is_active"):
            return playback["device"]
    except Exception as e:
        logger.debug(f"Error checking current playback device: {e}")

    try:
        devices_resp = sp.devices()
        devices = devices_resp.get("devices", []) if devices_resp else []
        for d in devices:
            if d.get("is_active"):
                return d

        # Fallback to Computer device if idle in background
        for d in devices:
            if d.get("type", "").lower() == "computer":
                logger.debug(f"Using idle Computer device fallback: {d.get('name')}")
                return d

        # Fallback to first available device
        if devices:
            logger.debug(f"Using first available device fallback: {devices[0].get('name')}")
            return devices[0]

    except Exception as e:
        logger.debug(f"Error checking Spotify devices list: {e}")

    return None


def play_track(query: str) -> str:
    """
    Searches Spotify for the given query and starts playback on the active device.
    Falls back to opening in browser/app if remote playback API is restricted or fails.
    """
    clean_query = query.strip() if query else ""
    # Strip common command noise
    clean_query = re.sub(r'^(?:play|put on)\s+', '', clean_query, flags=re.IGNORECASE)
    clean_query = re.sub(r'\s+on\s+spotify$', '', clean_query, flags=re.IGNORECASE).strip()

    if not clean_query:
        logger.debug("play_track called with empty query.")
        return "What would you like me to play on Spotify?"

    sp, err = get_spotify_client()
    if err:
        return err

    active_dev = get_active_device(sp)
    if not active_dev:
        logger.debug("No active Spotify session found when trying to play.")
        return "I don't see an active Spotify session — open Spotify on a device first."

    device_id = active_dev.get("id")

    try:
        # Search for track with limit=5 to get high quality top matches
        logger.debug(f"Searching Spotify for track query: '{clean_query}'")
        search_res = sp.search(q=clean_query, type="track", limit=5)
        tracks = search_res.get("tracks", {}).get("items", [])
        if not tracks:
            # Try searching with track: prefix
            search_res = sp.search(q=f"track:{clean_query}", type="track", limit=5)
            tracks = search_res.get("tracks", {}).get("items", [])

        if not tracks:
            logger.debug(f"No tracks found matching query: '{clean_query}'")
            return f"I couldn't find {clean_query} on Spotify."

        track = tracks[0]
        track_name = track.get("name", clean_query)
        artists = ", ".join(a.get("name", "") for a in track.get("artists", [])) or "Unknown Artist"
        track_uri = track.get("uri")
        track_url = track.get("external_urls", {}).get("spotify") or track_uri

        try:
            sp.transfer_playback(device_id=device_id, force_play=True)
        except Exception as t_err:
            logger.debug(f"Device wakeup transfer returned: {t_err}")

        try:
            sp.start_playback(device_id=device_id, uris=[track_uri])
        except Exception as start_err:
            logger.debug(f"sp.start_playback returned: {start_err}")

        # Ensure Windows Spotify application or browser triggers audio playback
        if track_uri and isinstance(track_uri, str):
            try:
                os.system(f'start {track_uri}')
            except Exception as sys_err:
                logger.debug(f"os.system start URI failed: {sys_err}")
                if track_url and isinstance(track_url, str):
                    webbrowser.open(track_url)

        logger.info(f"Started Spotify playback for '{track_name}' by '{artists}' on device '{active_dev.get('name')}'")
        return f"Playing {track_name} by {artists} on Spotify."

    except Exception as e:
        return _handle_spotify_exception(e, "play")


def pause_playback() -> str:
    """Pauses playback on the active Spotify device."""
    sp, err = get_spotify_client()
    if err:
        return err

    try:
        active_dev = get_active_device(sp)
        if not active_dev:
            logger.debug("No active Spotify session found when trying to pause.")
            return "I don't see an active Spotify session — open Spotify on a device first."

        sp.pause_playback(device_id=active_dev.get("id"))
        logger.info("Paused Spotify playback.")
        return "Pausing music."
    except Exception as e:
        return _handle_spotify_exception(e, "pause")


def resume_playback() -> str:
    """Resumes playback on the active Spotify device."""
    sp, err = get_spotify_client()
    if err:
        return err

    try:
        active_dev = get_active_device(sp)
        if not active_dev:
            logger.debug("No active Spotify session found when trying to resume.")
            return "I don't see an active Spotify session — open Spotify on a device first."

        sp.start_playback(device_id=active_dev.get("id"))
        logger.info("Resumed Spotify playback.")
        return "Resuming music."
    except Exception as e:
        return _handle_spotify_exception(e, "resume")


def next_track() -> str:
    """Skips to the next track on the active Spotify device."""
    sp, err = get_spotify_client()
    if err:
        return err

    try:
        active_dev = get_active_device(sp)
        if not active_dev:
            logger.debug("No active Spotify session found when trying to skip track.")
            return "I don't see an active Spotify session — open Spotify on a device first."

        sp.next_track(device_id=active_dev.get("id"))
        logger.info("Skipped to next Spotify track.")
        return "Skipping to the next song."
    except Exception as e:
        return _handle_spotify_exception(e, "skip")


def previous_track() -> str:
    """Goes back to the previous track on the active Spotify device."""
    sp, err = get_spotify_client()
    if err:
        return err

    try:
        active_dev = get_active_device(sp)
        if not active_dev:
            logger.debug("No active Spotify session found when trying to go to previous track.")
            return "I don't see an active Spotify session — open Spotify on a device first."

        sp.previous_track(device_id=active_dev.get("id"))
        logger.info("Went back to previous Spotify track.")
        return "Going back to the previous song."
    except Exception as e:
        return _handle_spotify_exception(e, "previous")


def _handle_spotify_exception(e: Exception, action: str) -> str:
    """Translates Spotify exceptions into user-friendly spoken feedback."""
    err_str = str(e).lower()
    logger.exception(f"Error during Spotify {action}: {e}")

    if "premium" in err_str or "restriction" in err_str or "403" in err_str:
        return "Spotify playback control requires a Spotify Premium account."
    if "no_active_device" in err_str or "device" in err_str or "not found" in err_str or "404" in err_str:
        return "I don't see an active Spotify session — open Spotify on a device first."

    return "I encountered an error controlling Spotify."
