import time
import speech_recognition as sr
from logger import logger

WAKE_WORDS = [
    "hey deeks", "hey deek", "deeks", "deek", "hey geeks", "hey geek",
    "geeks", "geek", "hey ducks", "hey duck", "hey deep", "hey peaks",
    "hey dix", "dix", "dex", "hey dex", "a deeks", "hey days", "hay days",
    "hey dicks", "hey dick", "hey decks", "hey deck", "hey disk",
    "hey digs", "hey duke", "hi deeks", "hi deek", "hello deeks",
    "okay deeks", "ok deeks"
]

def is_wake_word_match(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    if any(w in text_lower for w in WAKE_WORDS):
        return True
    if "deek" in text_lower or "deeks" in text_lower:
        return True
    return False

def start_background_wake_word_listener(callback):
    """
    Starts a background daemon thread that listens for the wake word ('Hey Deeks').
    When detected, it calls callback(True, direct_command_text).
    Returns a stop_listening function which must be called to stop the background thread.
    """
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.5
    recognizer.energy_threshold = 150
    recognizer.dynamic_energy_threshold = True

    source = sr.Microphone()
    try:
        # Fast ambient noise calibration
        with source as s:
            recognizer.adjust_for_ambient_noise(s, duration=0.2)
    except Exception as e:
        logger.error(f"Failed to calibrate microphone for background wake word: {e}")

    def _audio_callback(r, audio):
        try:
            google_text = r.recognize_google(audio)
            if google_text:
                if is_wake_word_match(google_text):
                    logger.info(f"Background wake word detected ('{google_text}').")
                    cleaned = google_text
                    for w in WAKE_WORDS:
                        cleaned = cleaned.lower().replace(w, "").strip()
                    
                    if len(cleaned) > 3:
                        callback(True, cleaned)
                    else:
                        callback(True, None)
                    return
        except sr.UnknownValueError:
            pass
        except Exception as e:
            logger.debug(f"Background recognition error: {e}")

    # Start listening in background with short 5s phrase limit for quick turnaround
    stop_listening = recognizer.listen_in_background(source, _audio_callback, phrase_time_limit=5)
    return stop_listening


def get_microphone_info() -> str:
    """Returns a string summary of active microphone for debugging."""
    try:
        mics = sr.Microphone.list_microphone_names()
        return f"Default mic active. Total system input devices: {len(mics)}"
    except Exception as e:
        return f"Could not list microphones: {e}"

def listen(max_retries=1, retry_delay=0.3, timeout=8, phrase_time_limit=15):
    """
    Listens for speech using Google Speech Recognition.
    Optimized for fast detection (0.5s pause threshold) and instant return.
    Includes a retry loop on OSError when opening sr.Microphone() to handle
    transient device-busy states after releasing previous streams.
    """
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.35
    recognizer.phrase_threshold = 0.1
    recognizer.non_speaking_duration = 0.2
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_adjustment_damping = 0.15
    recognizer.dynamic_energy_ratio = 1.5
    recognizer.energy_threshold = 150

    source_ctx = None
    source = None
    mic_open_retries = 2
    mic_retry_delay = 0.18  # 180ms delay between mic open attempts

    for attempt in range(mic_open_retries + 1):
        try:
            source_ctx = sr.Microphone()
            source = source_ctx.__enter__()
            break
        except OSError as e:
            if attempt < mic_open_retries:
                logger.warning(
                    f"[Stage 1/4: Mic Busy Retry] Device busy or opening error (attempt {attempt + 1}/{mic_open_retries + 1}). "
                    f"Retrying in {int(mic_retry_delay * 1000)}ms... Error: {e}"
                )
                time.sleep(mic_retry_delay)
            else:
                logger.error(f"[Mic Hardware Error] Microphone OS/Hardware error after {mic_open_retries + 1} attempts: {e}")
                return "error_mic"
        except Exception as e:
            logger.exception(f"[Mic Unexpected Error] Error during microphone initialization: {e}")
            return "error_unknown"

    try:
        logger.info("[Stage 1/4: Mic Open] Calibrating for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=0.1)
        # Freeze dynamic energy threshold after calibration so sensitivity remains stable
        recognizer.dynamic_energy_threshold = False
        recognizer.energy_threshold = max(70, min(recognizer.energy_threshold, 220))
        logger.info(f"[Stage 1/4: Mic Calibrated] Ambient energy threshold set to: {recognizer.energy_threshold:.1f}")
        print(f"[Mic active - Energy threshold: {recognizer.energy_threshold:.1f}]")
        
        logger.info(f"[Stage 2/4: Listening] Waiting for user speech (timeout={timeout}s)...")
        print("[Listening for command... Speak now!]")
        
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            logger.warning(f"[Stage 2/4: Timeout] No speech detected before {timeout}-second timeout.")
            print("[No speech detected within timeout]")
            return None

        audio_len = len(audio.frame_data) if hasattr(audio, 'frame_data') else 0
        logger.info(f"[Stage 3/4: Audio Captured] Received {audio_len} bytes. Processing...")
        print(f"[Audio captured ({audio_len} bytes). Processing...]")

        for attempt in range(max_retries + 1):
            try:
                text = recognizer.recognize_google(audio)
                logger.info(f"[Stage 4/4: Recognized] Google Speech Recognition successfully transcribed: '{text}'")
                return text
            except sr.UnknownValueError:
                logger.warning("[Stage 4/4: Unknown Value] Audio was heard, but speech could not be understood.")
                return None
            except sr.RequestError as e:
                if attempt < max_retries:
                    logger.warning(f"[Stage 4/4: Network Retry] Speech recognition network request failed (attempt {attempt + 1}/{max_retries + 1}). Retrying in {retry_delay}s... Error: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.warning(f"[Stage 4/4: Network Failed] Speech recognition failed after {max_retries + 1} attempts: {e}")
                    return "error_internet"
    except Exception as e:
        logger.exception(f"[Mic Unexpected Error] Error during speech recognition: {e}")
        return "error_unknown"
    finally:
        if source_ctx is not None:
            try:
                source_ctx.__exit__(None, None, None)
            except Exception:
                pass
