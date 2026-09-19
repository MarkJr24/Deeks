import os
import sys
import asyncio
import tempfile
import concurrent.futures

# Suppress pygame welcome banner
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import edge_tts
import pygame
from logger import logger
from memory.memory import load_memory

# Default and recommended natural neural voices
DEFAULT_VOICE = os.getenv("DEEKS_VOICE", "en-US-AriaNeural")

RECOMMENDED_VOICES = {
    "aria": "en-US-AriaNeural",      # Natural, expressive US female voice (Default)
    "jenny": "en-US-JennyNeural",    # Warm, friendly conversational US female voice
    "ava": "en-US-AvaNeural",        # Modern, bright US female voice
    "sonia": "en-GB-SoniaNeural",    # Crisp, professional British female voice
}

_mixer_initialized = False

def _init_mixer():
    """Initializes the pygame mixer once."""
    global _mixer_initialized
    if not _mixer_initialized:
        try:
            pygame.mixer.init()
            _mixer_initialized = True
        except Exception as e:
            logger.warning(f"Failed to initialize pygame mixer: {e}")

_init_mixer()

def _run_coroutine(coro):
    """Safely runs an async coroutine even if an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        return asyncio.run(coro)

async def _generate_audio(text: str, voice: str, output_path: str):
    """Generates audio for given text using edge-tts and writes to output_path."""
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)

def speak(text: str, voice: str = None, force: bool = False):
    """
    Speaks the given text using Microsoft Edge's natural neural TTS (edge-tts)
    and plays it smoothly via pygame mixer with automatic temp file cleanup.
    If meeting_mode is active, audio is suppressed to avoid interrupting calls.
    """
    if not text or not str(text).strip():
        return

    text_to_speak = str(text).strip()

    # Check Meeting Mode protection
    try:
        if not force and load_memory("meeting_mode"):
            logger.info(f"[Meeting Mode Active] Suppressing audio output: '{text_to_speak}'")
            print(f"\n[Meeting Mode Silent Output]: {text_to_speak}")
            return
    except Exception:
        pass

    selected_voice = voice or DEFAULT_VOICE
    selected_voice = voice or DEFAULT_VOICE
    temp_file_path = None

    try:
        _init_mixer()

        # Create a unique temporary mp3 file
        fd, temp_file_path = tempfile.mkstemp(suffix=".mp3", prefix="deeks_tts_")
        os.close(fd)

        # Generate neural TTS audio
        _run_coroutine(_generate_audio(text_to_speak, selected_voice, temp_file_path))

        # Play audio smoothly
        pygame.mixer.music.load(temp_file_path)
        pygame.mixer.music.play()
        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(30)

        pygame.mixer.music.unload()

    except Exception as e:
        logger.exception(f"TTS speak failure with edge-tts for text '{text_to_speak}': {e}")
        logger.info("Falling back to offline TTS (pyttsx3)")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text_to_speak)
            engine.runAndWait()
        except Exception as fallback_e:
            logger.exception(f"Fallback offline TTS also failed: {fallback_e}")
    finally:
        # Guarantee removal of temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                os.remove(temp_file_path)
            except Exception as e:
                logger.debug(f"Failed to clean up temporary audio file '{temp_file_path}': {e}")
