"""
skills/reminders.py — Persistent reminder system for Deeks
Supports:
  • One-time reminders: "remind me to <msg> in X minutes/hours"
  • One-time reminders: "remind me to <msg> at HH:MM / 5 pm"
  • Recurring daily  : "remind me every day to <msg> at HH:MM / 5 pm"
  • Cancel all       : "cancel my reminders"

Architecture
  - All reminders are stored in data/reminders.json (survives restarts).
  - A single background thread runs the `schedule` library loop.
  - Due reminders call _speak_cb (injected at startup) to fire TTS
    without touching the main conversation loop.
  - timer_skill.py is NOT touched.
"""

import os
import re
import json
import uuid
import time
import threading
import schedule
from datetime import datetime, timedelta

from logger import logger

# ── Storage ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ── Speak callback (injected at init) ─────────────────────────────────────────
_speak_cb = None   # set by init_reminders()

# ── Internal state ────────────────────────────────────────────────────────────
_lock = threading.Lock()          # guards file + schedule mutations
_scheduler_started = False


# ─────────────────────────────────────────────────────────────────────────────
#  JSON persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_reminders() -> list:
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[Reminders] Could not read reminders file: {e}")
        return []


def _save_reminders(reminders: list) -> None:
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)
    except Exception as e:
        logger.error(f"[Reminders] Could not save reminders file: {e}")


def _remove_reminder_by_id(rid: str) -> None:
    """Remove a one-time reminder from storage after it fires."""
    reminders = _load_reminders()
    reminders = [r for r in reminders if r.get("id") != rid]
    _save_reminders(reminders)


# ─────────────────────────────────────────────────────────────────────────────
#  Scheduler thread
# ─────────────────────────────────────────────────────────────────────────────

def _scheduler_loop():
    """Daemon thread: runs the schedule library event loop."""
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"[Reminders] Scheduler loop error: {e}")
        time.sleep(1)


def _ensure_scheduler_running():
    global _scheduler_started
    if not _scheduler_started:
        t = threading.Thread(target=_scheduler_loop, daemon=True, name="reminders-scheduler")
        t.start()
        _scheduler_started = True
        logger.info("[Reminders] Scheduler thread started.")


# ─────────────────────────────────────────────────────────────────────────────
#  Internal reminder firing
# ─────────────────────────────────────────────────────────────────────────────

def _fire_reminder(message: str, rid: str):
    """Called by the scheduler when a reminder is due."""
    try:
        logger.info(f"[Reminders] Firing reminder '{rid}': {message}")
        if _speak_cb:
            _speak_cb(f"Reminder: {message}")
        else:
            print(f"\n[REMINDER] {message}")
        # Remove from persistent storage (one-time reminders)
        _remove_reminder_by_id(rid)
    except Exception as e:
        logger.error(f"[Reminders] Error firing reminder: {e}")
    # schedule returns schedule.CancelJob to auto-cancel a one-time job
    return schedule.CancelJob


# ─────────────────────────────────────────────────────────────────────────────
#  Scheduling helpers
# ─────────────────────────────────────────────────────────────────────────────

def _schedule_one_time_delay(message: str, delay_seconds: float) -> str:
    """Schedule a one-time reminder that fires after delay_seconds."""
    rid = str(uuid.uuid4())

    def job():
        return _fire_reminder(message, rid)

    run_at = datetime.now() + timedelta(seconds=delay_seconds)
    time_str = run_at.strftime("%H:%M:%S")
    # schedule.every().day.at() runs once per day; we use .once-style via a
    # tagged job that returns CancelJob after firing.
    with _lock:
        schedule.every().day.at(time_str).do(job).tag(rid)

    # Persist
    reminders = _load_reminders()
    reminders.append({
        "id": rid,
        "type": "one_time",
        "message": message,
        "run_at_iso": run_at.isoformat(),
    })
    _save_reminders(reminders)
    logger.info(f"[Reminders] One-time reminder '{rid}' scheduled at {time_str}.")
    return rid


def _schedule_one_time_at(message: str, run_at: datetime) -> str:
    """Schedule a one-time reminder that fires at an absolute datetime."""
    rid = str(uuid.uuid4())

    def job():
        return _fire_reminder(message, rid)

    time_str = run_at.strftime("%H:%M:%S")
    with _lock:
        schedule.every().day.at(time_str).do(job).tag(rid)

    reminders = _load_reminders()
    reminders.append({
        "id": rid,
        "type": "one_time",
        "message": message,
        "run_at_iso": run_at.isoformat(),
    })
    _save_reminders(reminders)
    logger.info(f"[Reminders] One-time reminder '{rid}' scheduled at {time_str}.")
    return rid


def _schedule_recurring(message: str, time_str_hhmm: str) -> str:
    """Schedule a recurring daily reminder at HH:MM."""
    rid = str(uuid.uuid4())

    def job():
        try:
            logger.info(f"[Reminders] Firing recurring reminder '{rid}': {message}")
            if _speak_cb:
                _speak_cb(f"Reminder: {message}")
            else:
                print(f"\n[DAILY REMINDER] {message}")
        except Exception as e:
            logger.error(f"[Reminders] Error firing recurring reminder: {e}")

    with _lock:
        schedule.every().day.at(time_str_hhmm).do(job).tag(rid)

    reminders = _load_reminders()
    reminders.append({
        "id": rid,
        "type": "recurring",
        "message": message,
        "time_hhmm": time_str_hhmm,
    })
    _save_reminders(reminders)
    logger.info(f"[Reminders] Recurring daily reminder '{rid}' scheduled at {time_str_hhmm}.")
    return rid


# ─────────────────────────────────────────────────────────────────────────────
#  Startup reload
# ─────────────────────────────────────────────────────────────────────────────

def _reload_saved_reminders():
    """Called at startup to restore reminders from disk."""
    reminders = _load_reminders()
    valid = []
    now = datetime.now()

    for r in reminders:
        rid = r.get("id")
        rtype = r.get("type")
        message = r.get("message", "")

        if rtype == "recurring":
            time_str = r.get("time_hhmm", "")
            if time_str:
                def make_recurring_job(msg, tag):
                    def job():
                        try:
                            logger.info(f"[Reminders] Firing recurring '{tag}': {msg}")
                            if _speak_cb:
                                _speak_cb(f"Reminder: {msg}")
                        except Exception as e:
                            logger.error(f"[Reminders] Recurring fire error: {e}")
                    return job

                with _lock:
                    schedule.every().day.at(time_str).do(make_recurring_job(message, rid)).tag(rid)
                valid.append(r)
                logger.info(f"[Reminders] Restored recurring reminder '{rid}' at {time_str}.")

        elif rtype == "one_time":
            run_at_iso = r.get("run_at_iso")
            if not run_at_iso:
                continue
            try:
                run_at = datetime.fromisoformat(run_at_iso)
            except ValueError:
                continue

            if run_at <= now:
                logger.info(f"[Reminders] Skipping past one-time reminder '{rid}' ({run_at_iso}).")
                continue  # skip — don't keep it

            time_str = run_at.strftime("%H:%M:%S")

            def make_one_time_job(msg, tag):
                def job():
                    return _fire_reminder(msg, tag)
                return job

            with _lock:
                schedule.every().day.at(time_str).do(make_one_time_job(message, rid)).tag(rid)
            valid.append(r)
            logger.info(f"[Reminders] Restored one-time reminder '{rid}' at {time_str}.")

    _save_reminders(valid)
    logger.info(f"[Reminders] Reload complete. {len(valid)} reminder(s) restored.")


# ─────────────────────────────────────────────────────────────────────────────
#  Time parsing
# ─────────────────────────────────────────────────────────────────────────────

_TIME_RE = re.compile(
    r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
    re.IGNORECASE
)


def _parse_absolute_time(text: str) -> datetime | None:
    """
    Parse expressions like '5 pm', '17:30', '5:30 pm' from text.
    Returns a datetime for today (or tomorrow if already past).
    Returns None if no time found.
    """
    m = _TIME_RE.search(text)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3).lower() if m.group(3) else None

    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)  # already passed today → schedule for tomorrow
    return target


def _parse_relative_delay(text: str) -> float | None:
    """
    Parse 'in X minutes', 'in X hours', 'in X and a half minutes', etc.
    Returns total delay in seconds, or None if no match.
    """
    # Match patterns like: "in 5 minutes", "in 2 hours", "in 90 seconds"
    m = re.search(
        r'in\s+(\d+(?:\.\d+)?)\s*(second|seconds|minute|minutes|hour|hours)',
        text, re.IGNORECASE
    )
    if not m:
        return None

    value = float(m.group(1))
    unit = m.group(2).lower()

    if "second" in unit:
        return value
    elif "minute" in unit:
        return value * 60
    elif "hour" in unit:
        return value * 3600
    return None


def _extract_message(text: str, reminder_type: str) -> str:
    """
    Strip all command words from text to get the reminder message.
    """
    cleaned = text

    if reminder_type == "recurring":
        # "remind me every day to <msg> at <time>"
        cleaned = re.sub(r'remind\s+me\s+every\s+day\s+to\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', cleaned, flags=re.IGNORECASE)
    elif reminder_type == "at":
        # "remind me to <msg> at <time>"
        cleaned = re.sub(r'remind\s+me\s+to\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', cleaned, flags=re.IGNORECASE)
    elif reminder_type == "in":
        # "remind me to <msg> in X minutes/hours"
        cleaned = re.sub(r'remind\s+me\s+to\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+in\s+\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?)', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip(" .,")


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def init_reminders(speak_callback) -> None:
    """
    Call once at Deeks startup.
    Injects the speak function, reloads saved reminders, and starts the scheduler.
    """
    global _speak_cb
    _speak_cb = speak_callback
    _ensure_scheduler_running()
    _reload_saved_reminders()
    logger.info("[Reminders] Reminder system initialised.")


def process_reminder_command(clean_text: str) -> str:
    """
    Parse and act on a reminder voice command.
    Returns a confirmation string to speak back to the user.
    """
    text = clean_text.strip().lower()

    # ── Cancel all ────────────────────────────────────────────────────────────
    if any(p in text for p in ["cancel my reminders", "cancel all reminders",
                                "remove my reminders", "delete my reminders",
                                "clear my reminders"]):
        return _cmd_cancel_all()

    # ── Recurring daily ───────────────────────────────────────────────────────
    if re.search(r'every\s+day', text, re.IGNORECASE):
        return _cmd_recurring(text)

    # ── One-time relative ("in X minutes/hours") ──────────────────────────────
    if "remind me" in text and re.search(r'\bin\s+\d', text):
        return _cmd_one_time_relative(text)

    # ── One-time absolute ("at X pm") ─────────────────────────────────────────
    if "remind me" in text and re.search(r'\bat\s+\d', text):
        return _cmd_one_time_at(text)

    return "I didn't catch when to remind you, can you try again?"


def _cmd_cancel_all() -> str:
    reminders = _load_reminders()
    count = len(reminders)
    if count == 0:
        return "You have no active reminders to cancel."

    # Clear all scheduled jobs
    with _lock:
        schedule.clear()
    _save_reminders([])
    logger.info(f"[Reminders] Cancelled all {count} reminder(s).")
    noun = "reminder" if count == 1 else "reminders"
    return f"Done. Cancelled {count} {noun}."


def _cmd_recurring(text: str) -> str:
    target = _parse_absolute_time(text)
    if target is None:
        return "I didn't catch when to remind you, can you try again?"

    message = _extract_message(text, "recurring")
    if not message:
        return "I didn't catch what to remind you about, can you try again?"

    time_hhmm = target.strftime("%H:%M")
    _schedule_recurring(message, time_hhmm)

    display = target.strftime("%I:%M %p").lstrip("0")
    return f"Got it. I'll remind you every day to {message} at {display}."


def _cmd_one_time_relative(text: str) -> str:
    delay = _parse_relative_delay(text)
    if delay is None or delay <= 0:
        return "I didn't catch when to remind you, can you try again?"

    message = _extract_message(text, "in")
    if not message:
        return "I didn't catch what to remind you about, can you try again?"

    _schedule_one_time_delay(message, delay)

    # Human-friendly confirmation
    if delay < 60:
        unit_str = f"{int(delay)} second{'s' if delay != 1 else ''}"
    elif delay < 3600:
        mins = delay / 60
        unit_str = f"{mins:.0f} minute{'s' if mins != 1 else ''}"
    else:
        hrs = delay / 3600
        unit_str = f"{hrs:.1f} hour{'s' if hrs != 1 else ''}"

    return f"Sure, I'll remind you to {message} in {unit_str}."


def _cmd_one_time_at(text: str) -> str:
    target = _parse_absolute_time(text)
    if target is None:
        return "I didn't catch when to remind you, can you try again?"

    message = _extract_message(text, "at")
    if not message:
        return "I didn't catch what to remind you about, can you try again?"

    _schedule_one_time_at(message, target)

    display_time = target.strftime("%I:%M %p").lstrip("0")
    tomorrow = (datetime.now() + timedelta(days=1)).date() == target.date()
    when = f"tomorrow at {display_time}" if tomorrow else f"at {display_time}"
    return f"Sure, I'll remind you to {message} {when}."
