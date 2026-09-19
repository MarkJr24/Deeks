import re
from logger import logger

def _get_volume_control():
    """Returns the pycaw AudioEndpointVolume interface safely across pycaw versions."""
    import comtypes
    comtypes.CoInitialize()
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    devices = AudioUtilities.GetSpeakers()
    if hasattr(devices, "EndpointVolume"):
        return devices.EndpointVolume
    else:
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)

def set_volume(percent: float) -> str:
    """Sets system volume to a percentage between 0 and 100."""
    try:
        vol = _get_volume_control()
        percent = max(0.0, min(100.0, float(percent)))
        scalar = percent / 100.0
        vol.SetMasterVolumeLevelScalar(scalar, None)
        int_val = int(round(percent))
        return f"Volume set to {int_val} percent."
    except Exception as e:
        logger.exception(f"Error setting volume to {percent}%: {e}")
        return "I couldn't adjust the volume right now."

def change_volume(delta_percent: float) -> str:
    """Increases or decreases volume by delta_percent (e.g. +10 or -10)."""
    try:
        vol = _get_volume_control()
        current_scalar = vol.GetMasterVolumeLevelScalar()
        current_percent = current_scalar * 100.0
        new_percent = max(0.0, min(100.0, current_percent + delta_percent))
        vol.SetMasterVolumeLevelScalar(new_percent / 100.0, None)
        int_val = int(round(new_percent))
        if delta_percent > 0:
            return f"Volume increased to {int_val} percent."
        else:
            return f"Volume decreased to {int_val} percent."
    except Exception as e:
        logger.exception(f"Error changing volume by {delta_percent}%: {e}")
        return "I couldn't adjust the volume right now."

def mute_volume() -> str:
    """Mutes the system volume."""
    try:
        vol = _get_volume_control()
        vol.SetMute(1, None)
        return "Muted."
    except Exception as e:
        logger.exception(f"Error muting volume: {e}")
        return "I couldn't adjust the volume right now."

def unmute_volume() -> str:
    """Unmutes the system volume."""
    try:
        vol = _get_volume_control()
        vol.SetMute(0, None)
        return "Unmuted."
    except Exception as e:
        logger.exception(f"Error unmuting volume: {e}")
        return "I couldn't adjust the volume right now."

WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "max": 100, "maximum": 100, "full": 100, "half": 50, "min": 0, "minimum": 0
}

def process_volume_command(text: str) -> str:
    """
    Parses voice commands for volume control and executes appropriate volume function.
    Returns response string to be spoken.
    """
    text_lower = text.lower().strip()

    if "unmute" in text_lower or "turn sound back on" in text_lower:
        return unmute_volume()
    elif "mute" in text_lower or "silence" in text_lower:
        return mute_volume()
    elif any(phrase in text_lower for phrase in ["volume up", "turn it up", "turn up", "increase volume", "raise volume", "louder"]):
        return change_volume(10.0)
    elif any(phrase in text_lower for phrase in ["volume down", "turn it down", "turn down", "decrease volume", "lower volume", "quieter"]):
        return change_volume(-10.0)
    elif "set volume" in text_lower or "volume to" in text_lower or "change volume to" in text_lower:
        digits = re.findall(r'\b\d+\b', text_lower)
        if digits:
            return set_volume(float(digits[0]))
        for word, val in WORD_TO_NUM.items():
            if re.search(rf'\b{word}\b', text_lower):
                return set_volume(float(val))

        return "I didn't catch the volume percentage."

    return "I couldn't adjust the volume."
