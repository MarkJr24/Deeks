from logger import logger

try:
    from pynput.keyboard import Key, Controller
    _keyboard = Controller()
    _HAS_PYNPUT = True
except ImportError:
    _keyboard = None
    _HAS_PYNPUT = False

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


def play_pause_media() -> str:
    """
    Simulates pressing the Play/Pause media key.
    Works universally across browser video players (YouTube), Spotify, local media players, etc.
    """
    logger.info("Triggering Play/Pause media key")
    try:
        if _HAS_PYNPUT and _keyboard:
            _keyboard.tap(Key.media_play_pause)
            return "Toggled media playback."
        elif _HAS_PYAUTOGUI:
            pyautogui.press("playpause")
            return "Toggled media playback."
        else:
            logger.error("Neither pynput nor pyautogui is available for media key simulation.")
            return "Unable to control media key: missing keyboard controller library."
    except Exception as e:
        logger.exception(f"Error sending Play/Pause media key: {e}")
        return "Failed to trigger Play/Pause key."


def next_track_media() -> str:
    """
    Simulates pressing the Next Track media key.
    """
    logger.info("Triggering Next Track media key")
    try:
        if _HAS_PYNPUT and _keyboard:
            _keyboard.tap(Key.media_next)
            return "Skipped to next track."
        elif _HAS_PYAUTOGUI:
            pyautogui.press("nexttrack")
            return "Skipped to next track."
        else:
            logger.error("Neither pynput nor pyautogui is available for media key simulation.")
            return "Unable to control media key: missing keyboard controller library."
    except Exception as e:
        logger.exception(f"Error sending Next Track media key: {e}")
        return "Failed to trigger Next Track key."


def previous_track_media() -> str:
    """
    Simulates pressing the Previous Track media key.
    """
    logger.info("Triggering Previous Track media key")
    try:
        if _HAS_PYNPUT and _keyboard:
            _keyboard.tap(Key.media_previous)
            return "Went back to previous track."
        elif _HAS_PYAUTOGUI:
            pyautogui.press("prevtrack")
            return "Went back to previous track."
        else:
            logger.error("Neither pynput nor pyautogui is available for media key simulation.")
            return "Unable to control media key: missing keyboard controller library."
    except Exception as e:
        logger.exception(f"Error sending Previous Track media key: {e}")
        return "Failed to trigger Previous Track key."
