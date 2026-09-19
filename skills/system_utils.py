import os
import datetime
import ctypes
import subprocess
from logger import logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")

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
