import os
import re
import json
from datetime import datetime, timedelta
from logger import logger

SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory", "schedule.json")

def _load_events() -> list:
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Error loading schedule file: {e}")
        return []

def _save_events(events: list) -> bool:
    try:
        os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=4)
        return True
    except Exception as e:
        logger.exception(f"Error saving schedule file: {e}")
        return False

def parse_relative_date(text: str) -> tuple[str, str, str]:
    """
    Finds and resolves date keywords (today, tomorrow, day names, etc.) in text.
    Returns (resolved_YYYY_MM_DD, display_day_name, cleaned_text_without_date).
    """
    today = datetime.now().date()
    text_lower = text.lower()
    
    # 1. Check 'tomorrow'
    if "tomorrow" in text_lower:
        target_date = today + timedelta(days=1)
        cleaned = re.sub(r'\b(for|on)?\s*tomorrow\b', '', text, flags=re.IGNORECASE)
        return target_date.strftime("%Y-%m-%d"), "tomorrow", cleaned.strip()
        
    # 2. Check 'today' / 'tonight'
    if "today" in text_lower or "tonight" in text_lower:
        target_date = today
        cleaned = re.sub(r'\b(for|on)?\s*(today|tonight)\b', '', text, flags=re.IGNORECASE)
        return target_date.strftime("%Y-%m-%d"), "today", cleaned.strip()
        
    # 3. Check days of week (e.g., 'on Monday', 'next Friday')
    days_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, day_idx in days_map.items():
        pattern = rf'\b(?:on|this|next)?\s*{day_name}\b'
        if re.search(pattern, text_lower):
            current_day = today.weekday()
            days_ahead = (day_idx - current_day) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week's day
            target_date = today + timedelta(days=days_ahead)
            cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE)
            return target_date.strftime("%Y-%m-%d"), day_name.capitalize(), cleaned.strip()

    # Default to today if no date specified
    return today.strftime("%Y-%m-%d"), "today", text.strip()

def parse_time(text: str) -> tuple[str, str, str]:
    """
    Extracts time expression (e.g. 'at 3pm', 'at 3:30 pm', 'at 11 am', 'at 5 o'clock') from text.
    Returns (sortable_HH_MM, display_time, cleaned_text_without_time).
    """
    # Match patterns like: at 3:30 pm, at 3pm, at 3 pm, 3:30pm, at 14:00
    time_regex = r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|o\'clock)?\b'
    match = re.search(time_regex, text, re.IGNORECASE)
    
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3).lower() if match.group(3) else None
        
        # Handle 12-hour AM/PM conversion
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
            
        sortable_time = f"{hour:02d}:{minute:02d}"
        
        # Format nice display time (e.g. "3:00 PM")
        dt = datetime.strptime(sortable_time, "%H:%M")
        display_time = dt.strftime("%I:%M %p").lstrip("0")
        
        cleaned = text[:match.start()] + text[match.end():]
        return sortable_time, display_time, cleaned.strip()

    return "00:00", "All Day", text.strip()

def add_event_from_text(text: str) -> tuple[bool, str]:
    """
    Parses a voice command such as:
    'add an event tomorrow at 3pm dentist appointment'
    'add event today at 5pm grocery shopping'
    'schedule meeting with John tomorrow at 2:30 pm'
    """
    try:
        # Strip command prefixes
        cleaned = re.sub(r'^(?:please\s+)?(?:add\s+(?:an?\s+)?(?:event|to\s+(?:my\s+)?schedule)|schedule|create\s+(?:an?\s+)?event)\s*', '', text, flags=re.IGNORECASE).strip()
        
        date_iso, day_label, text_after_date = parse_relative_date(cleaned)
        time_sortable, time_display, text_after_time = parse_time(text_after_date)
        
        # Clean up remaining text as description
        description = re.sub(r'^(?:for|called|named|to|about|at|on)\s+', '', text_after_time, flags=re.IGNORECASE).strip('.,! ')
        if not description:
            description = "General event"
            
        events = _load_events()
        new_event = {
            "date": date_iso,
            "time": time_sortable,
            "time_display": time_display,
            "description": description
        }
        events.append(new_event)
        # Sort events chronologically
        events.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
        _save_events(events)
        
        logger.info(f"Added event: {new_event}")
        
        if time_display == "All Day":
            response = f"Added {description} for {day_label}."
        else:
            response = f"Added {description} for {day_label} at {time_display}."
            
        return True, response
    except Exception as e:
        logger.exception(f"Error adding event from text '{text}': {e}")
        return False, "I couldn't understand the event details."

def get_schedule(date_keyword_or_text: str = "today") -> str:
    """
    Retrieves events for a given day (today, tomorrow, or text query).
    Returns a spoken response string.
    """
    try:
        date_iso, day_label, _ = parse_relative_date(date_keyword_or_text)
        events = _load_events()
        
        matching = [e for e in events if e.get("date") == date_iso]
        matching.sort(key=lambda x: x.get("time", ""))
        
        if not matching:
            return f"You have nothing scheduled for {day_label}."
            
        if len(matching) == 1:
            ev = matching[0]
            if ev.get("time_display") == "All Day":
                return f"For {day_label}, you have {ev['description']}."
            return f"On your schedule for {day_label}: at {ev['time_display']}, {ev['description']}."
            
        # Multiple events
        parts = []
        for ev in matching:
            if ev.get("time_display") == "All Day":
                parts.append(f"{ev['description']}")
            else:
                parts.append(f"at {ev['time_display']}, {ev['description']}")
                
        return f"You have {len(matching)} events for {day_label}: " + "; and ".join(parts) + "."
    except Exception as e:
        logger.exception(f"Error fetching schedule for '{date_keyword_or_text}': {e}")
        return "I encountered an error looking up your schedule."

def clear_schedule(target_day: str = None) -> str:
    """
    Clears schedule events.
    If target_day is provided (e.g. 'today', 'tomorrow'), clears events for that day.
    If target_day is None or 'all', clears all schedule events.
    """
    try:
        events = _load_events()
        if not events:
            return "Your schedule is already clear."

        if target_day and target_day.lower() not in ["all", "everything"]:
            date_iso, day_label, _ = parse_relative_date(target_day)
            remaining = [e for e in events if e.get("date") != date_iso]
            removed_count = len(events) - len(remaining)
            if removed_count == 0:
                return f"You had no appointments scheduled for {day_label}."
            _save_events(remaining)
            logger.info(f"Cleared {removed_count} schedule event(s) for {day_label}.")
            return f"Cleared all appointments for {day_label}."
        else:
            _save_events([])
            logger.info("Cleared all schedule events.")
            return "Cleared all your appointments and schedule events."
    except Exception as e:
        logger.exception(f"Error clearing schedule: {e}")
        return "I encountered an error clearing your schedule."
