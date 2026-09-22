"""
skills/reminders.py — Persistent reminder system for Deeks
Supports:
  • One-time reminders: "remind me to <msg> in X minutes/hours"
  • One-time reminders: "remind me to <msg> at HH:MM / 5 pm"
  • One-time reminders: "remind me about <msg> on October 5th at 9am"
  • Recurring daily  : "remind me every day to <msg> at HH:MM / 5 pm"
  • List reminders   : "what reminders do I have", "list my reminders"
  • Cancel all       : "cancel my reminders"
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

MONTHS_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12
}

DAYS_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}

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
    with _lock:
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

def _schedule_one_time_at(message: str, run_at: datetime) -> str:
    """Schedule a one-time reminder that fires at an absolute datetime."""
    rid = str(uuid.uuid4())

    def job():
        # Check if the target date has arrived (schedule.every().day.at() runs daily)
        if datetime.now() < run_at - timedelta(seconds=30):
            return
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
    logger.info(f"[Reminders] One-time reminder '{rid}' ('{message}') scheduled for {run_at.isoformat()} at {time_str}.")
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

    with _lock:
        # Clear any previously registered schedule jobs before reloading
        schedule.clear()

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
                    continue  # skip — past reminder

                time_str = run_at.strftime("%H:%M:%S")

                def make_one_time_job(msg, tag, target_dt):
                    def job():
                        if datetime.now() < target_dt - timedelta(seconds=30):
                            return
                        return _fire_reminder(msg, tag)
                    return job

                schedule.every().day.at(time_str).do(make_one_time_job(message, rid, run_at)).tag(rid)
                valid.append(r)
                logger.info(f"[Reminders] Restored one-time reminder '{rid}' at {time_str} for {run_at_iso}.")

        _save_reminders(valid)
    logger.info(f"[Reminders] Reload complete. {len(valid)} reminder(s) restored.")


# ─────────────────────────────────────────────────────────────────────────────
#  Parsing logic
# ─────────────────────────────────────────────────────────────────────────────

def _parse_relative_delay(text: str) -> float | None:
    """
    Parse 'in X seconds/minutes/hours'.
    Returns total delay in seconds, or None if no match.
    """
    m = re.search(
        r'\bin\s+(\d+(?:\.\d+)?)\s*(second|seconds|minute|minutes|hour|hours)\b',
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


def _extract_clean_message(text: str, date_str: str = "", time_str: str = "", is_relative: bool = False) -> str:
    """
    Strips command prefixes, date substrings, and time substrings to isolate the reminder message.
    """
    cleaned = text.strip()
    cleaned = re.sub(r'^(?:please\s+)?remind\s+me\s+(?:every\s+day\s+)?(?:to|about|for|on|at)?\s*', '', cleaned, flags=re.IGNORECASE)

    if is_relative:
        cleaned = re.sub(r'\s+in\s+\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*to\s+', '', cleaned, flags=re.IGNORECASE)
    else:
        if date_str:
            cleaned = re.sub(rf'\b(?:on|for|this|next)?\s*{re.escape(date_str)}\b', '', cleaned, flags=re.IGNORECASE)
        if time_str:
            cleaned = re.sub(rf'\b(?:at\s+)?{re.escape(time_str)}\b', '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'^\s*(?:to|about|for|on|at)\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+(?:to|about|for|on|at)\s*$', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip(" .,!?:;")


def _parse_datetime_and_message(text: str) -> tuple[datetime | None, str | None, str]:
    """
    Parses datetime and reminder message from voice input text.
    Returns (target_datetime, reminder_type, message).
    reminder_type can be: "one_time", "recurring", or None if invalid.
    """
    logger.info(f"[Reminders] Attempting to parse reminder input: '{text}'")
    raw_text = text.strip()
    text_lower = raw_text.lower()

    is_recurring = bool(re.search(r'\bevery\s+day\b', text_lower))

    # 1. Parse relative delay ("in X minutes/hours/seconds")
    delay_sec = _parse_relative_delay(text_lower)
    if delay_sec is not None and delay_sec > 0:
        target_dt = datetime.now() + timedelta(seconds=delay_sec)
        msg = _extract_clean_message(raw_text, is_relative=True)
        logger.info(f"[Reminders] Parsed relative delay ({delay_sec}s) -> target_dt: {target_dt.isoformat()}, message: '{msg}'")
        return target_dt, "one_time", msg

    # 2. Parse date component
    now = datetime.now()
    target_date = None
    date_matched_str = ""

    if "tomorrow" in text_lower:
        target_date = (now + timedelta(days=1)).date()
        date_matched_str = "tomorrow"
    elif "today" in text_lower or "tonight" in text_lower:
        target_date = now.date()
        date_matched_str = "today"
    else:
        # Check day names (e.g. "on Friday", "this Saturday")
        for day_name, day_idx in DAYS_MAP.items():
            if re.search(rf'\b{day_name}\b', text_lower):
                current_day = now.weekday()
                days_ahead = (day_idx - current_day) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = (now + timedelta(days=days_ahead)).date()
                date_matched_str = day_name
                break

        # Check explicit month & day (e.g. "October 5th", "5th of October", "Oct 5")
        if not target_date:
            for m_name, m_num in MONTHS_MAP.items():
                m_pattern = rf'\b{m_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b'
                m_match = re.search(m_pattern, text_lower)
                if m_match:
                    day_val = int(m_match.group(1))
                    year_val = now.year
                    try:
                        candidate_date = datetime(year_val, m_num, day_val).date()
                        if candidate_date < now.date():
                            candidate_date = datetime(year_val + 1, m_num, day_val).date()
                        target_date = candidate_date
                        date_matched_str = m_match.group(0)
                        break
                    except ValueError:
                        pass

                m_pattern_rev = rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{m_name}\b'
                m_match_rev = re.search(m_pattern_rev, text_lower)
                if m_match_rev:
                    day_val = int(m_match_rev.group(1))
                    year_val = now.year
                    try:
                        candidate_date = datetime(year_val, m_num, day_val).date()
                        if candidate_date < now.date():
                            candidate_date = datetime(year_val + 1, m_num, day_val).date()
                        target_date = candidate_date
                        date_matched_str = m_match_rev.group(0)
                        break
                    except ValueError:
                        pass

    # 3. Parse time component
    hour = None
    minute = 0
    time_matched_str = ""

    # Pattern A: 9am, 9:30am, 9 pm, 9:30 pm, at 9 am, at 9:30 pm
    t_match = re.search(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', text_lower)
    if t_match:
        hour = int(t_match.group(1))
        minute = int(t_match.group(2)) if t_match.group(2) else 0
        ampm = t_match.group(3).lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        time_matched_str = t_match.group(0)
    else:
        # Pattern B: "at 9", "at 14:30"
        t_match_at = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\b', text_lower)
        if t_match_at:
            hour = int(t_match_at.group(1))
            minute = int(t_match_at.group(2)) if t_match_at.group(2) else 0
            time_matched_str = t_match_at.group(0)
        else:
            # Pattern C: "9:30"
            t_match_colon = re.search(r'\b(\d{1,2}):(\d{2})\b', text_lower)
            if t_match_colon:
                hour = int(t_match_colon.group(1))
                minute = int(t_match_colon.group(2))
                time_matched_str = t_match_colon.group(0)
            else:
                # Pattern D: "9 o'clock"
                t_match_oclock = re.search(r'\b(\d{1,2})\s*o\'?clock\b', text_lower)
                if t_match_oclock:
                    hour = int(t_match_oclock.group(1))
                    time_matched_str = t_match_oclock.group(0)

    if hour is None or not (0 <= hour <= 23 and 0 <= minute <= 59):
        logger.warning(f"[Reminders] Could not parse valid time from input: '{text}' (date_found='{date_matched_str}')")
        return None, None, ""

    msg = _extract_clean_message(raw_text, date_str=date_matched_str, time_str=time_matched_str)

    if is_recurring:
        target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        logger.info(f"[Reminders] Parsed recurring reminder at {hour:02d}:{minute:02d}, message: '{msg}'")
        return target_dt, "recurring", msg

    if not target_date:
        target_date = now.date()

    target_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If no explicit date was matched and the target time has passed today, schedule for tomorrow
    if not date_matched_str and target_dt <= now:
        target_dt += timedelta(days=1)

    logger.info(f"[Reminders] Parsed one-time reminder for {target_dt.isoformat()}, message: '{msg}'")
    return target_dt, "one_time", msg


# ─────────────────────────────────────────────────────────────────────────────
#  Public API & Command Dispatcher
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


def _cmd_list_reminders() -> str:
    """Read and format all currently saved reminders from data/reminders.json."""
    reminders = _load_reminders()
    if not reminders:
        return "You don't have any reminders set"

    items = []
    now = datetime.now()

    for r in reminders:
        msg = r.get("message", "Untitled reminder")
        rtype = r.get("type")

        if rtype == "recurring":
            time_hhmm = r.get("time_hhmm", "")
            if time_hhmm:
                try:
                    dt = datetime.strptime(time_hhmm, "%H:%M")
                    time_disp = dt.strftime("%I:%M %p").lstrip("0")
                except Exception:
                    time_disp = time_hhmm
                items.append(f"every day at {time_disp} to {msg}")
        elif rtype == "one_time":
            run_at_iso = r.get("run_at_iso", "")
            if run_at_iso:
                try:
                    run_at = datetime.fromisoformat(run_at_iso)
                    time_disp = run_at.strftime("%I:%M %p").lstrip("0")
                    if run_at.date() == now.date():
                        when = f"today at {time_disp}"
                    elif run_at.date() == (now + timedelta(days=1)).date():
                        when = f"tomorrow at {time_disp}"
                    else:
                        date_str = run_at.strftime("%B %d").replace(" 0", " ")
                        when = f"on {date_str} at {time_disp}"
                    items.append(f"to {msg} {when}")
                except Exception:
                    items.append(f"to {msg}")

    if not items:
        return "You don't have any reminders set"

    if len(items) == 1:
        return f"You have 1 reminder set: {items[0]}."

    formatted_items = []
    for i, item in enumerate(items, 1):
        formatted_items.append(f"Reminder {i}: {item}")

    return f"You have {len(items)} reminders set. " + ". ".join(formatted_items) + "."


def _cmd_cancel_all() -> str:
    reminders = _load_reminders()
    count = len(reminders)
    if count == 0:
        return "You have no active reminders to cancel."

    with _lock:
        schedule.clear()
        _save_reminders([])
    logger.info(f"[Reminders] Cancelled all {count} reminder(s).")
    noun = "reminder" if count == 1 else "reminders"
    return f"Done. Cancelled {count} {noun}."


def process_reminder_command(clean_text: str) -> str:
    """
    Parse and act on a reminder voice command.
    Returns a confirmation string to speak back to the user.
    """
    text = clean_text.strip().lower()
    logger.info(f"[Reminders] process_reminder_command received: '{text}'")

    # ── 1. List Reminders ────────────────────────────────────────────────────
    list_phrases = [
        "what reminders do i have", "what are my reminders", "list my reminders",
        "list reminders", "show my reminders", "check my reminders",
        "do i have any reminders", "view reminders", "get reminders",
        "all reminders", "show reminders"
    ]
    if any(p in text for p in list_phrases) or (("list" in text or "what" in text or "show" in text or "check" in text) and "reminder" in text and "remind me to" not in text and "remind me in" not in text and "remind me at" not in text):
        return _cmd_list_reminders()

    # ── 2. Cancel All ─────────────────────────────────────────────────────────
    if any(p in text for p in ["cancel my reminders", "cancel all reminders",
                                "remove my reminders", "delete my reminders",
                                "clear my reminders"]):
        return _cmd_cancel_all()

    # ── 3. Parse & Add Reminder ───────────────────────────────────────────────
    target_dt, rtype, message = _parse_datetime_and_message(clean_text)

    if target_dt is None or not message or rtype is None:
        logger.warning(f"[Reminders] Failed to parse reminder from input: '{text}' (target_dt={target_dt}, rtype={rtype}, message='{message}')")
        return "I couldn't understand when or what to remind you about. Please specify a time, like 'tomorrow at 9 am' or 'in 10 minutes'."

    if rtype == "recurring":
        time_hhmm = target_dt.strftime("%H:%M")
        rid = _schedule_recurring(message, time_hhmm)
        display = target_dt.strftime("%I:%M %p").lstrip("0")
        logger.info(f"[Reminders] Saved recurring reminder '{rid}' for message '{message}' at {time_hhmm}")
        return f"Got it. I'll remind you every day to {message} at {display}."

    elif rtype == "one_time":
        now = datetime.now()
        delay_seconds = (target_dt - now).total_seconds()

        if delay_seconds <= -60:  # allow 60s tolerance for clock seconds
            logger.warning(f"[Reminders] Target datetime {target_dt.isoformat()} has already passed for input '{text}'")
            return "That time has already passed. Please specify a future time or date."

        rid = _schedule_one_time_at(message, target_dt)
        logger.info(f"[Reminders] Saved one-time reminder '{rid}' for message '{message}' at {target_dt.isoformat()}")

        display_time = target_dt.strftime("%I:%M %p").lstrip("0")
        tomorrow = (now + timedelta(days=1)).date() == target_dt.date()
        today = now.date() == target_dt.date()

        if today:
            when = f"today at {display_time}"
        elif tomorrow:
            when = f"tomorrow at {display_time}"
        else:
            date_str = target_dt.strftime("%B %d").replace(" 0", " ")
            when = f"on {date_str} at {display_time}"

        return f"Sure, I'll remind you to {message} {when}."

    return "I couldn't understand when to remind you. Please try again."
