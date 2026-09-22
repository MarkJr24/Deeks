# pyrefly: ignore [missing-import]
import json
import re
import ollama
from logger import logger

INTENT_SYSTEM_PROMPT = """You are the Intent Classification engine for Deeks, a personal voice assistant.
Your task is to classify the user's spoken input into exactly ONE of the following valid intent labels and extract relevant parameters.

VALID INTENTS:
- EXIT: Stop, quit, exit, or turn off Deeks.
- SHUTDOWN_PC: Shutdown or turn off the computer.
- RESTART_PC: Restart or reboot the computer.
- LOCK_PC: Lock the PC screen/workstation.
- SCREENSHOT: Take a screenshot.
- MEETING_MODE_ON: Enable meeting mode / mute assistant.
- MEETING_MODE_OFF: Disable meeting mode / unmute assistant.
- VOLUME_ADJUST: Turn volume up/down, mute, unmute, set volume level.
- BRIEFING: Give daily briefing / summary of today.
- BRIEFING_SCHEDULE: Schedule daily briefing time.
- WEATHER: Check weather. Extract "city" if mentioned, else null.
- SCHEDULE_GET: View schedule / agenda for today, tomorrow, or a specific day. Extract "day" if mentioned.
- SCHEDULE_ADD: Add an event to schedule. Extract "event_text".
- SCHEDULE_CLEAR: Clear, delete, or wipe schedule events/appointments. Extract "day" if mentioned (e.g. "today", "tomorrow", "all").
- NEWS: Fetch headlines / news updates.
- SEARCH: Web search / look up information on Google/web. Extract "query".
- REMINDER: Set or cancel a reminder. Extract "reminder_text".
- TIMER: Set a timer for X minutes. Extract "minutes" (numeric or word).
- CLIPBOARD_READ: Read text from clipboard.
- NOTES_SAVE: Save a note or remember something into notes. Extract "note_text".
- NOTES_READ: Read back saved notes.
- NOTES_CLEAR: Clear/delete saved notes.
- MEMORY_SAVE: Remember a persistent fact about the user. Extract "fact_text".
- MEMORY_READ: Recall what user asked to remember.
- TIME: Ask current time.
- OPEN_APP: Open or launch an application. Extract "app_name".
- CLOSE_APP: Close or quit an application. Extract "app_name".
- OPEN_WEBSITE: Open a specific website. Extract "site_name".
- SPOTIFY_PLAY: Play a specific song, artist, album, or playlist on Spotify. Extract "query".
- SPOTIFY_PAUSE: Pause music playback explicitly on Spotify.
- SPOTIFY_RESUME: Resume music playback explicitly on Spotify.
- SPOTIFY_NEXT: Skip to next song explicitly on Spotify.
- SPOTIFY_PREVIOUS: Go back to previous song explicitly on Spotify.
- MEDIA_PLAY_PAUSE: Play or pause video / media playback (YouTube, video, media player, generic play/pause).
- MEDIA_NEXT: Skip or go to next video / media track (generic skip/next).
- MEDIA_PREVIOUS: Go back to previous video / media track (generic previous/go back).
- FILE_OPEN: Open a file or folder by name. Extract "target_name".
- FILE_CREATE_FOLDER: Create a new folder. Extract "folder_name".
- FILE_DELETE: Delete or trash a file or folder. Extract "target_name".
- FILE_RENAME: Rename a file or folder. Extract "old_name", "new_name".
- GENERAL_QUERY: General question, chat, knowledge query, or anything not covered above.

OUTPUT FORMAT:
Respond ONLY with a valid, single-line JSON object. No explanation, no markdown backticks, no extra text.
Example JSON:
{"intent": "WEATHER", "params": {"city": "London"}}
{"intent": "LOCK_PC", "params": {}}
{"intent": "REMINDER", "params": {"reminder_text": "take vitamins at 8 am"}}
{"intent": "GENERAL_QUERY", "params": {}}
"""

def classify_intent(text: str) -> dict:
    """
    Classifies a natural speech sentence into a Deeks intent using Ollama (phi4-mini).
    Returns a dict: {"intent": str, "params": dict}
    Defaults to {"intent": "GENERAL_QUERY", "params": {}} on error or timeout.
    """
    if not text or not text.strip():
        return {"intent": "GENERAL_QUERY", "params": {}}

    try:
        response = ollama.chat(
            model='phi4-mini',
            messages=[
                {'role': 'system', 'content': INTENT_SYSTEM_PROMPT},
                {'role': 'user', 'content': text}
            ],
            options={'temperature': 0.0, 'num_predict': 40}
        )

        content = response['message']['content'].strip()
        # Remove any markdown formatting if present
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        # Parse JSON
        parsed = json.loads(content)
        intent = parsed.get("intent", "GENERAL_QUERY").upper()
        params = parsed.get("params", {})

        logger.info(f"Intent classified as '{intent}' with params {params} for query: '{text}'")
        return {"intent": intent, "params": params}

    except Exception as e:
        logger.warning(f"Intent classification failed for '{text}' (falling back to GENERAL_QUERY): {e}")
        return {"intent": "GENERAL_QUERY", "params": {}}
