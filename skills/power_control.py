import os
import time
from logger import logger

def handle_power_command(action: str, speak_func, listen_func) -> bool:
    """
    Handles shutdown or restart with interactive confirmation and a 5-second countdown.
    
    :param action: "shutdown" or "restart"
    :param speak_func: callable to speak text out loud (e.g. main.speak)
    :param listen_func: callable to listen for speech input (e.g. main.listen)
    :return: True if executed/handled successfully, False otherwise.
    """
    if action not in ["shutdown", "restart"]:
        return False

    action_word = "shut down" if action == "shutdown" else "restart"
    action_title = "Shutdown" if action == "shutdown" else "Restart"

    try:
        # 1. Ask for confirmation out loud
        prompt = f"Are you sure you want to {action_word}? Say yes to confirm."
        logger.info(f"[Power Control] Prompting user: '{prompt}'")
        speak_func(prompt)

        # 2. Listen for confirmation
        response = listen_func()
        logger.info(f"[Power Control] User response: '{response}'")

        # 3. Verify confirmation
        if response and any(kw in response.lower() for kw in ["yes", "confirm", "yeah", "yep", "sure", "do it"]):
            if action == "shutdown":
                countdown_msg = "Shutting down in 5... 4... 3... 2... 1..."
            else:
                countdown_msg = "Restarting in 5... 4... 3... 2... 1..."

            logger.info(f"[Power Control] Confirmed. Speaking countdown: '{countdown_msg}'")
            speak_func(countdown_msg)

            cmd = "shutdown /s /t 0" if action == "shutdown" else "shutdown /r /t 0"
            logger.info(f"[Power Control] Executing OS command: {cmd}")
            os.system(cmd)
            return True
        else:
            cancel_msg = f"{action_title} cancelled."
            logger.info(f"[Power Control] Not confirmed. Speaking: '{cancel_msg}'")
            speak_func(cancel_msg)
            return True

    except Exception as e:
        logger.exception(f"Error executing power command '{action}': {e}")
        try:
            speak_func("I couldn't do that right now.")
        except Exception:
            pass
        return False
