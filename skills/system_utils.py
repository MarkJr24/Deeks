import os
import time
import datetime
import ctypes
import subprocess
from logger import logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")

# ── Cache for check_meeting_apps_running() — refreshed every 20 s ──────────
_meeting_cache: dict = {"value": False, "ts": 0.0}
_MEETING_CACHE_TTL = 20  # seconds

def check_meeting_apps_running() -> bool:
    """Checks if common video call / meeting applications are running.
    Result is cached for 20 s to avoid spawning a tasklist subprocess every loop.
    """
    global _meeting_cache
    now = time.time()
    if now - _meeting_cache["ts"] < _MEETING_CACHE_TTL:
        return _meeting_cache["value"]
    try:
        output = subprocess.check_output(
            "tasklist", shell=True, text=True, errors="ignore", timeout=3
        ).lower()
        meeting_apps = ["zoom.exe", "teams.exe", "ms-teams.exe", "msteams.exe",
                        "webexhost.exe", "ciscocollabhost.exe", "skype.exe"]
        result = any(app in output for app in meeting_apps)
    except Exception:
        result = False
    _meeting_cache = {"value": result, "ts": now}
    return result

def ensure_ollama_running() -> bool:
    """
    Checks if Ollama server is running on http://localhost:11434/.
    If not responding, automatically launches 'ollama serve' as a hidden background process.
    """
    import urllib.request
    try:
        req = urllib.request.urlopen("http://localhost:11434/", timeout=1)
        if req.status == 200:
            return True
    except Exception:
        pass

    try:
        logger.info("Ollama server not detected on localhost:11434. Auto-launching 'ollama serve' in background...")
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to auto-launch Ollama server: {e}")
        return False


def lock_pc() -> bool:
    """
    Locks the Windows user session using ctypes.windll.user32.LockWorkStation(),
    with a fallback to rundll32.exe user32.dll,LockWorkStation.
    Returns True if successfully executed, False otherwise.
    """
    try:
        res = ctypes.windll.user32.LockWorkStation()
        if res != 0:
            logger.info("Windows workstation locked successfully via LockWorkStation API.")
            return True
        logger.warning("ctypes.windll.user32.LockWorkStation returned 0 (failed). Attempting rundll32 fallback...")
    except Exception as e:
        logger.warning(f"ctypes.windll.user32.LockWorkStation exception: {e}. Attempting rundll32 fallback...")

    # Fallback method using system shell execution
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        logger.info("Windows workstation locked successfully via rundll32 fallback.")
        return True
    except Exception as e:
        logger.exception(f"Error locking PC via fallback: {e}")
        return False

def take_screenshot() -> str:
    """
    Captures the full screen using PIL.ImageGrab and saves it to screenshots/ folder.
    Returns spoken confirmation message.
    """
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)

        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(filepath, "PNG")
        logger.info(f"Screenshot saved successfully to: {filepath}")
        return "Screenshot saved"
    except Exception as e:
        logger.exception(f"Error taking screenshot: {e}")
        return "I couldn't take a screenshot right now"
