"""
skills/clipboard_notes.py — Clipboard and Notes skill for Deeks voice assistant.

Features:
1. Clipboard:
   - "read clipboard" / "what's on my clipboard" -> reads clipboard content using pyperclip.
   - Truncates long text (>500 chars) with "...and more".
   - Handles empty / non-text / errors gracefully.

2. Notes:
   - "remember this: [note text]" / "make a note: [note text]" -> saves note with timestamp to data/notes.json.
   - "read my notes" -> reads back all notes most-recent-first.
   - "clear my notes" -> deletes all notes and confirms count removed.
"""

import os
import re
import json
from datetime import datetime
import pyperclip
from logger import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")


def _ensure_data_dir():
    """Ensures that the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_notes() -> list:
    """Loads notes from data/notes.json."""
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.exception(f"Error reading notes file: {e}")
        return []


def _save_notes(notes: list) -> bool:
    """Saves notes list to data/notes.json."""
    try:
        _ensure_data_dir()
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.exception(f"Error writing notes file: {e}")
        return False


def read_clipboard() -> str:
    """
    Reads text content from system clipboard using pyperclip.
    Truncates at ~500 characters if too long.
    Returns spoken response message.
    """
    try:
        content = pyperclip.paste()
    except Exception as e:
        logger.exception(f"Error reading clipboard via pyperclip: {e}")
        return "I couldn't access the clipboard right now"

    if content is None or not isinstance(content, str) or not content.strip():
        return "There's nothing readable on your clipboard right now"

    text = content.strip()
    if len(text) > 500:
        truncated = text[:500].rstrip() + " ...and more"
        return truncated
    
    return text


def save_note(note_text: str) -> str:
    """
    Saves a note to data/notes.json with current timestamp.
    Returns spoken confirmation message.
    """
    clean_note = note_text.strip()
    if clean_note.startswith(":") or clean_note.startswith("-"):
        clean_note = clean_note.lstrip(": -").strip()

    if not clean_note:
        return "What note would you like me to save?"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes = _load_notes()
    notes.append({
        "text": clean_note,
        "timestamp": timestamp
    })

    if _save_notes(notes):
        logger.info(f"Saved new note: '{clean_note}' at {timestamp}")
        return "Got it, I've saved that"
    else:
        return "I couldn't save your note right now"


def read_notes() -> str:
    """
    Reads back all saved notes out loud, most recent first.
    Returns spoken response message.
    """
    notes = _load_notes()
    if not notes:
        return "You don't have any notes saved"

    reversed_notes = list(reversed(notes))
    if len(reversed_notes) == 1:
        return f"You have 1 note saved. Note 1: {reversed_notes[0]['text']}"

    items = [f"Note {i + 1}: {n['text']}" for i, n in enumerate(reversed_notes)]
    return f"You have {len(reversed_notes)} notes saved. " + ". ".join(items)


def clear_notes() -> str:
    """
    Deletes all saved notes and confirms how many were removed.
    Returns spoken response message.
    """
    notes = _load_notes()
    count = len(notes)
    if count == 0:
        return "You don't have any notes saved"

    if _save_notes([]):
        logger.info(f"Cleared {count} notes from {NOTES_FILE}")
        if count == 1:
            return "Cleared 1 saved note"
        else:
            return f"Cleared {count} saved notes"
    else:
        return "I couldn't clear your notes right now"


def process_clipboard_notes_command(clean_text: str, raw_text: str = "") -> tuple[bool, str]:
    """
    Main router function for clipboard and notes commands.
    Returns (handled: bool, speech_response: str).
    """
    text_to_check = clean_text.lower().strip()
    raw_to_check = raw_text.lower().strip() if raw_text else text_to_check

    # 1. Clipboard commands
    clipboard_keywords = [
        "read clipboard", "what's on my clipboard", "whats on my clipboard",
        "what is on my clipboard", "read my clipboard", "check clipboard"
    ]
    if any(k in text_to_check for k in clipboard_keywords):
        return True, read_clipboard()

    # 2. Read notes
    read_notes_keywords = [
        "read my notes", "read notes", "show my notes", "show notes",
        "what are my notes", "get my notes", "list my notes"
    ]
    if any(k in text_to_check for k in read_notes_keywords):
        return True, read_notes()

    # 3. Clear notes
    clear_notes_keywords = [
        "clear my notes", "clear notes", "delete my notes", "delete notes",
        "clear all notes", "delete all notes"
    ]
    if any(k in text_to_check for k in clear_notes_keywords):
        return True, clear_notes()

    # 4. Save note: "remember this: [note text]" or "make a note: [note text]"
    note_save_prefixes = ["remember this", "make a note"]
    if any(text_to_check.startswith(prefix) for prefix in note_save_prefixes):
        # Attempt extraction from raw_text first to preserve formatting/case if possible
        match = re.search(r'^(?:remember\s+this|make\s+a\s+note)(?::|\s+to|\s+that|\s+)(.+)$', raw_text, re.IGNORECASE)
        if not match:
            match = re.search(r'^(?:remember\s+this|make\s+a\s+note)(?::|\s+to|\s+that|\s+)(.+)$', text_to_check, re.IGNORECASE)

        note_text = match.group(1).strip() if match else ""
        return True, save_note(note_text)

    return False, ""
