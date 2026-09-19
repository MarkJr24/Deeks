import os
import sys
import re
import time
import json
import atexit
import signal
import ctypes
from datetime import datetime
from pynput import keyboard as pynput_keyboard

# ── Set process priority to BELOW_NORMAL so Deeks never dominates CPU ──────
try:
    BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(),
        BELOW_NORMAL_PRIORITY_CLASS
    )
except Exception:
    pass  # Non-critical — continue even if this fails

from logger import logger
from skills.voice_output import speak
from skills.voice_input import listen, start_background_wake_word_listener
from memory.memory import save_memory, load_memory, add_user_fact
from skills.llm_skill import handle_general_query
from skills.time_skill import get_current_time
from skills.search_skill import perform_search
from skills.open_app_skill import open_application, close_application, is_known_app
from skills.weather_skill import get_weather
from skills.schedule_skill import add_event_from_text, get_schedule
from skills.news_skill import get_top_headlines
from skills.briefing_skill import get_daily_briefing
from skills.volume_control import process_volume_command
from skills.system_utils import lock_pc, take_screenshot
from skills.power_control import handle_power_command
from skills.reminders import process_reminder_command, init_reminders
from skills.clipboard_notes import process_clipboard_notes_command

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_DIR = os.path.join(BASE_DIR, "logs")
STATUS_FILE = os.path.join(LOG_DIR, "status.json")
PID_FILE = os.path.join(LOG_DIR, "deeks.pid")

# ── Cache for check_meeting_apps_running() — refreshed every 20 s ──────────
_meeting_cache: dict = {"value": False, "ts": 0.0}
_MEETING_CACHE_TTL = 20  # seconds

def check_meeting_apps_running() -> bool:
    """Checks if common video call / meeting applications are running.
    Result is cached for 20 s to avoid spawning a tasklist subprocess every loop.
    """
    global _meeting_cache
    now = time.time()
    if now - _meeting_cache["ts"] < _MEETING_CACHE_TTL:
        return _meeting_cache["value"]
    try:
        import subprocess
        output = subprocess.check_output(
            "tasklist", shell=True, text=True, errors="ignore", timeout=3
        ).lower()
        meeting_apps = ["zoom.exe", "teams.exe", "ms-teams.exe", "msteams.exe",
                        "webexhost.exe", "ciscocollabhost.exe", "skype.exe"]
        result = any(app in output for app in meeting_apps)
    except Exception:
        result = False
    _meeting_cache = {"value": result, "ts": now}
    return result

def update_status(is_running=True):
    """Writes runtime status and heartbeat to logs/status.json and logs/deeks.pid."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        now_str = datetime.now().isoformat()
        
        status_data = {
            "pid": os.getpid() if is_running else None,
            "status": "running" if is_running else "stopped",
            "is_running": is_running,
            "last_heartbeat": now_str,
            "hotkey": "Ctrl+Alt+D"
        }
        
        if is_running:
            if not os.path.exists(STATUS_FILE):
                status_data["start_time"] = now_str
            else:
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        status_data["start_time"] = old_data.get("start_time", now_str)
                except Exception:
                    status_data["start_time"] = now_str
                    
            with open(PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        else:
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass

        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to update status file: {e}")

def cleanup():
    """Cleanly marks status as stopped on exit."""
    logger.info("Deeks assistant is shutting down...")
    update_status(is_running=False)

# Register cleanup on normal exit or signals
atexit.register(cleanup)
try:
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
except Exception:
    pass

def clean_user_input(text: str) -> str:
    """Normalize input by removing conversational filler, polite prefixes/suffixes, and wake words."""
    cleaned = text.lower().strip()
    # Remove leading wake word variations if present (e.g., 'hey deeks', 'deeks', 'assistant')
    cleaned = re.sub(r'^(?:hey\s+|ok\s+|okay\s+)?(?:deeks|assistant)[,\s]*', '', cleaned).strip()
    # Remove leading polite phrases (e.g., 'can you', 'could you please', 'please', 'would you mind')
    cleaned = re.sub(r'^(?:can you|could you|please|would you mind|will you|would you|kindly)\s+(?:please\s+)?', '', cleaned).strip()
    # Remove trailing polite phrases
    cleaned = re.sub(r'\s+(?:please|for me|right now|thank you|thanks)$', '', cleaned).strip()
    return cleaned


def execute_command(text: str) -> bool:
    """
    Executes a parsed voice command.
    Returns True to continue running, or False if a shutdown command was given.
    """
    text_lower = text.lower()
    clean_text = clean_user_input(text)
    logger.info(f"Processing command: '{text}' (normalized: '{clean_text}')")
    
    exit_phrases = [
        "goodbye", "good bye", "bye", "bye bye", "bye-bye",
        "exit deeks", "exit assistant", "exit",
        "stop deeks", "stop assistant", "stop listening",
        "quit deeks", "quit assistant", "quit",
        "turn off deeks", "turn off assistant",
        "shut down deeks", "shutdown deeks", "close deeks"
    ]
    if clean_text in exit_phrases or any(p in clean_text for p in ["goodbye", "good bye", "exit deeks", "stop deeks", "quit deeks", "shut down deeks", "turn off deeks", "close deeks"]):
        speak("Goodbye! Shutting down.")
        return False

        
    elif any(p in clean_text for p in ["shut down the pc", "shutdown the pc", "shut down my computer", "shutdown computer", "shut down", "shutdown", "turn off the pc", "turn off my pc"]):
        return handle_power_command("shutdown", speak, listen)

    elif any(p in clean_text for p in ["restart the pc", "restart my computer", "restart computer", "restart", "reboot the pc", "reboot"]):
        return handle_power_command("restart", speak, listen)
        
    elif any(phrase in clean_text for phrase in ["enable meeting mode", "meeting mode on", "enter meeting mode", "i am in a meeting", "i'm in a meeting", "mute deeks", "do not disturb"]):
        save_memory("meeting_mode", True)
        speak("Meeting mode enabled. Background voice activation and speech are muted until you exit meeting mode.", force=True)
        print("\n[Meeting Mode ENABLED - Deeks is muted and wake word paused]")
        return True
        
    elif any(phrase in clean_text for phrase in ["disable meeting mode", "meeting mode off", "exit meeting mode", "meeting finished", "meeting over", "unmute deeks"]):
        save_memory("meeting_mode", False)
        speak("Meeting mode disabled. I am back online.", force=True)
        print("\n[Meeting Mode DISABLED - Normal operations resumed]")
        return True

    elif any(p in clean_text for p in ["volume", "turn it up", "turn it down", "turn up", "turn down", "louder", "quieter", "mute", "unmute"]):
        try:
            response_text = process_volume_command(clean_text)
            speak(response_text)
        except Exception as e:
            logger.exception(f"Error processing volume command: {e}")
            speak("I couldn't adjust the volume right now.")

    elif re.search(r'\block\b.*\b(?:pc|computer|screen|workstation)\b', clean_text) or any(p in clean_text for p in ["lock pc", "lock screen", "lock computer"]):
        try:
            speak("Locking your PC")
            lock_pc()
        except Exception as e:
            logger.exception(f"Error locking PC: {e}")
            speak("I couldn't lock your PC right now.")


    elif any(p in clean_text for p in ["take a screenshot", "screenshot this", "take screenshot", "screenshot"]):
        try:
            msg = take_screenshot()
            speak(msg)
        except Exception as e:
            logger.exception(f"Error taking screenshot: {e}")
            speak("I couldn't take a screenshot right now.")
        
    elif any(p in clean_text for p in ["schedule", "set", "every day"]) and "briefing" in clean_text:
        m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', clean_text, re.IGNORECASE)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3).lower() if m.group(3) else None
            
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
                
            scheduled_time = f'{hour:02d}:{minute:02d}'
            save_memory("daily_briefing_time", scheduled_time)
            
            # Formatting for human reading
            display_time = datetime.strptime(scheduled_time, "%H:%M").strftime("%I:%M %p").lstrip("0")
            speak(f"I've scheduled your daily briefing for {display_time} every day.")
            logger.info(f"Scheduled daily briefing for {scheduled_time}")
        else:
            speak("I didn't catch the time you want it scheduled for.")
            
    elif any(p in clean_text for p in [
        "brief", "briefing", "daily briefing", "brief me", "my briefing", "give me a briefing",
        "morning briefing", "evening briefing", "daily update",
        "what's for today", "whats for today", "what's today", "whats today",
        "what's on today", "whats on today", "what's up today", "whats up today",
        "what do i have today", "what's happening today", "run me through today",
        "today's briefing", "today's update", "today's plan", "plan for today",
        "what's my day", "whats my day", "summarize my day", "how does today look"
    ]):
        try:
            briefing_text = get_daily_briefing()
            speak(briefing_text)
        except Exception as e:
            logger.exception(f"Error generating daily briefing: {e}")
            speak("I encountered an error generating your daily briefing.")
            
    elif "weather" in clean_text:
        try:
            city = None
            match = re.search(r'weather\s+(?:like\s+)?(?:in|for|at)\s+([a-zA-Z\s]+)', clean_text)
            if match:
                city = match.group(1).strip()
            
            if not city:
                city = load_memory("default_city")
                
            if not city:
                city = "Chennai"
                save_memory("default_city", "Chennai")
            
            result = get_weather(city)
            if result.get("success"):
                speak(result["summary"])
            else:
                speak(result.get("error", "I couldn't fetch the weather right now."))
        except Exception as e:
            logger.exception(f"Error processing weather command: {e}")
            speak("I encountered an error retrieving the weather.")
        
    elif any(phrase in clean_text for phrase in ["on my schedule", "my schedule", "on my agenda", "my agenda", "check schedule", "get schedule", "view schedule"]):
        try:
            date_keyword = "today"
            if "tomorrow" in clean_text:
                date_keyword = "tomorrow"
            elif any(d in clean_text for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    if d in clean_text:
                        date_keyword = d
                        break
                        
            schedule_msg = get_schedule(date_keyword)
            speak(schedule_msg)
        except Exception as e:
            logger.exception(f"Error checking schedule: {e}")
            speak("I encountered an error looking up your schedule.")
            
    elif any(clean_text.startswith(p) for p in ["add an event", "add event", "add to schedule", "add to my schedule", "schedule "]) or ("add" in clean_text and "event" in clean_text):
        try:
            success, msg = add_event_from_text(text)
            speak(msg)
        except Exception as e:
            logger.exception(f"Error adding schedule event: {e}")
            speak("I encountered an error saving that event.")
        
    elif any(phrase in clean_text for phrase in ["what's the news", "what is the news", "give me the headlines", "what are the headlines", "tell me the news", "latest news", "top headlines", "the headlines", "read the news"]):
        try:
            news_result = get_top_headlines()
            speak(news_result["summary"])
        except Exception as e:
            logger.exception(f"Error fetching news: {e}")
            speak("I encountered an error retrieving the news.")
            
    elif clean_text.startswith("search for ") or clean_text.startswith("google ") or clean_text.startswith("look up "):
        query = re.sub(r'^(?:search for|google|look up)\s+', '', clean_text).strip()
        try:
            speak("Here's what I found.")
            perform_search(query)
        except Exception as e:
            logger.exception(f"Error performing search for '{query}': {e}")
            speak("I encountered an error opening the search results.")
            
    elif clean_text.startswith("what is ") and "time" not in clean_text and "weather" not in clean_text and "schedule" not in clean_text and "news" not in clean_text:
        query = clean_text[len("what is "):].strip()
        try:
            speak("Here's what I found.")
            perform_search(query)
        except Exception as e:
            logger.exception(f"Error searching for '{query}': {e}")
            speak("I encountered an error searching for that.")
        
    elif any(p in clean_text for p in [
        "remind me", "cancel my reminders", "cancel all reminders",
        "remove my reminders", "delete my reminders", "clear my reminders"
    ]):
        try:
            response_text = process_reminder_command(clean_text)
            speak(response_text)
        except Exception as e:
            logger.exception(f"Error processing reminder command: {e}")
            speak("I encountered an error setting that reminder.")

    elif "set a timer for" in clean_text or "set timer for" in clean_text:
        try:
            match = re.search(r'set (?:a )?timer for (\w+|\d+) minute', clean_text)
            if match:
                val = match.group(1)
                minutes = 0
                word_to_num = {
                    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                    "a": 1, "an": 1, "half": 0.5
                }
                if val.isdigit():
                    minutes = float(val)
                elif val in word_to_num:
                    minutes = word_to_num[val]
                
                if minutes > 0:
                    from skills.timer_skill import start_timer
                    
                    def timer_finished():
                        try:
                            import pythoncom
                            pythoncom.CoInitialize()
                            import win32com.client
                            speaker = win32com.client.Dispatch("SAPI.SpVoice")
                            logger.info("Timer finished!")
                            print("\n[Timer finished!]")
                            speaker.Speak("Time is up!")
                        except Exception:
                            # Fallback if pywin32 fails
                            try:
                                import pyttsx3
                                engine = pyttsx3.init()
                                logger.info("Timer finished (fallback TTS)!")
                                print("\n[Timer finished!]")
                                engine.say("Time is up!")
                                engine.runAndWait()
                            except Exception as err:
                                logger.exception(f"Error speaking timer notification: {err}")

                    start_timer(minutes, timer_finished)
                    speak(f"Timer set for {val} minutes.")
                else:
                    speak("I didn't understand the number of minutes.")
            else:
                speak("I didn't catch the time for the timer.")
        except Exception as e:
            logger.exception(f"Error processing timer command: {e}")
            speak("I encountered an error setting the timer.")
        
    elif any(k in clean_text for k in ["clipboard", "remember this", "make a note", "read my notes", "read notes", "show my notes", "clear my notes", "clear notes", "delete my notes"]):
        try:
            handled, msg = process_clipboard_notes_command(clean_text, text)
            if handled:
                speak(msg)
            else:
                speak("I didn't understand that clipboard or notes command.")
        except Exception as e:
            logger.exception(f"Error processing clipboard/notes command: {e}")
            speak("I encountered an error processing your request.")

    elif clean_text.startswith("remember ") or clean_text.startswith("remember that "):

        try:
            thing_to_remember = re.sub(r'^remember(?:\s+that)?\s+', '', clean_text).strip()
            add_user_fact(thing_to_remember)
            logger.info(f"Saved memory fact: {thing_to_remember}")
            print(f"Saved memory: {thing_to_remember}")
            speak(f"Got it. I'll remember that {thing_to_remember}")
        except Exception as e:
            logger.exception(f"Error saving memory fact: {e}")
            speak("I encountered an error saving that to memory.")
        
    elif "what did i tell you to remember" in clean_text or "what did i ask you to remember" in clean_text:
        try:
            recalled = load_memory("last_thing")
            if recalled:
                logger.info(f"Recalled memory: {recalled}")
                print(f"Recalled: {recalled}")
                speak(f"You told me to remember: {recalled}")
            else:
                speak("I don't have anything saved in my memory yet.")
        except Exception as e:
            logger.exception(f"Error loading memory: {e}")
            speak("I encountered an error retrieving memory.")
            
    elif "what" in clean_text and "time" in clean_text:
        try:
            current_time = get_current_time()
            speak(f"The current time is {current_time}.")
        except Exception as e:
            logger.exception(f"Error fetching current time: {e}")
            speak("I encountered an error getting the current time.")
            
    elif any(phrase in clean_text for phrase in ["clear chat", "reset chat", "forget conversation", "clear history", "start new chat"]):
        # The LLM skill is stateless, but we acknowledge the command.
        speak("I've reset our conversation context. What would you like to talk about?")
        
    elif re.search(r'\b(?:close|quit)\b', clean_text) and not any(k in clean_text for k in ["chat", "history", "conversation"]):
        app_match = re.search(r'\b(?:close|quit)(?:\s+down)?\s+(.+)$', clean_text)
        if app_match:
            app_name = app_match.group(1).strip()
        else:
            app_name = re.sub(r'\b(?:close|quit)\b', '', clean_text).strip()
            
        app_name = re.sub(r'\b(please|for me|now|right now)\b', '', app_name).strip(' .')
        try:
            response_msg = close_application(app_name)
            speak(response_msg)
        except Exception as e:
            logger.exception(f"Error closing application '{app_name}': {e}")
            speak("I couldn't close that.")

    elif re.search(r'\b(?:open|launch|start|run)\b', clean_text) or is_known_app(clean_text):
        app_match = re.search(r'\b(?:open|launch|start|run)(?:\s+up)?\s+(.+)$', clean_text)
        if app_match:
            app_name = app_match.group(1).strip()
        else:
            app_name = clean_text
            
        app_name = re.sub(r'\b(please|for me|now|right now)\b', '', app_name).strip(' .')
        try:
            if open_application(app_name):
                speak(f"Opening {app_name}.")
            else:
                speak(f"I don't know how to open {app_name} yet.")
        except Exception as e:
            logger.exception(f"Error opening application '{app_name}': {e}")
            speak("I encountered an error trying to open that application.")
            
    else:
        logger.info(f"Processing query: '{text}'")
        try:
            llm_response = handle_general_query(text)
            speak(llm_response)
        except Exception as e:
            logger.exception(f"Error handling assistant query: {e}")
            speak("I'm not sure how to help with that right now.")

    return True

def main():
    logger.info("Deeks assistant is starting...")
    print("Deeks is starting...")
    update_status(is_running=True)
    
    try:
        speak("Hey, I'm online.")
    except Exception as e:
        logger.exception(f"Initial TTS greeting failed: {e}")
    
    # State variable to ensure internet warning is spoken only once when connection is down
    internet_warned = False
    
    import threading
    import queue
    
    trigger_queue = queue.Queue()
    
    def hotkey_callback():
        trigger_queue.put(("HOTKEY", None))
        
    try:
        hotkey_listener = pynput_keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+d': hotkey_callback
        })
        hotkey_listener.start()
        # Keep a reference to ensure it isn't garbage collected and can be stopped cleanly
        atexit.register(hotkey_listener.stop)
    except Exception as e:
        logger.exception(f"Failed to register keyboard hotkey: {e}")
        
    def wake_word_callback(triggered, command_text):
        if triggered:
            trigger_queue.put(("WAKE_WORD", command_text))
            
    def scheduled_briefing_thread():
        while True:
            try:
                briefing_time = load_memory("daily_briefing_time")
                if briefing_time:
                    now = datetime.now()
                    current_time_str = now.strftime("%H:%M")
                    current_date_str = now.strftime("%Y-%m-%d")
                    
                    last_briefing_date = load_memory("last_briefing_date")
                    
                    if current_time_str >= briefing_time and last_briefing_date != current_date_str:
                        logger.info(f"Auto-triggering scheduled daily briefing at {current_time_str}")
                        save_memory("last_briefing_date", current_date_str)
                        trigger_queue.put(("AUTO_SCHEDULED", "give me my daily briefing"))
                        
            except Exception as e:
                logger.error(f"Error in background scheduling thread: {e}")
            time.sleep(30)
            
    threading.Thread(target=scheduled_briefing_thread, daemon=True).start()

    # Initialise reminder system — reload saved reminders and start scheduler
    try:
        init_reminders(speak)
        logger.info("Reminder system ready.")
    except Exception as e:
        logger.exception(f"Failed to initialise reminders: {e}")
    
    print("\n[Deeks is active. Say 'Hey Deeks' or press Ctrl+Alt+D to speak a command]")
    
    last_interaction_time = 0
    _last_status_write = 0.0   # tracks last heartbeat disk write

    while True:
        try:
            # ── Throttled heartbeat: write status at most once every 30 s ──
            _now = time.time()
            if _now - _last_status_write >= 30:
                update_status(is_running=True)
                _last_status_write = _now

            is_meeting_mode = load_memory("meeting_mode") or check_meeting_apps_running()
            stop_listening = None
            
            # Start background listener for wake word ONLY when NOT in meeting mode!
            if not is_meeting_mode:
                stop_listening = start_background_wake_word_listener(wake_word_callback)
            else:
                logger.info("[Meeting Mode Protection] Background wake word listener paused to avoid call interference.")
            
            trigger_type = None
            command_text = None
            
            # Wait for any trigger (hotkey or wake word)
            while True:
                try:
                    trigger_type, command_text = trigger_queue.get(timeout=1.0)
                    break
                except queue.Empty:
                    pass  # just waiting — no disk write needed
                    
            # Stop the background listener so the main microphone can be used!
            if stop_listening:
                stop_listening(wait_for_stop=True)
            
            now_time = time.time()
            is_active_convo = (last_interaction_time > 0) and ((now_time - last_interaction_time) < 45)

            text = None

            if trigger_type == "HOTKEY":
                logger.info("=== [Hotkey Triggered: Ctrl+Alt+D] ===")
                print("\n[Hotkey pressed!]")
                try:
                    prompt_msg = "Yeah?" if is_active_convo else "Hey Mark, what's up?"
                    logger.info(f"[Hotkey Flow] Speaking prompt: '{prompt_msg}' (active_convo={is_active_convo})...")
                    speak(prompt_msg)
                    time.sleep(0.05)
                    logger.info("[Hotkey Flow] Prompt finished. Opening microphone to listen for command...")
                except Exception as e:
                    logger.exception(f"[Hotkey Flow] Error speaking prompt: {e}")
                
                text = listen()
                
            elif trigger_type == "WAKE_WORD":
                logger.info("=== [Wake Word Triggered] ===")
                print("\n[Wake Word detected!]")
                if command_text:
                    # User already said the command along with wake word
                    text = command_text
                else:
                    try:
                        prompt_msg = "Yeah?" if is_active_convo else "Hey Mark, what's up?"
                        logger.info(f"[Wake Word Flow] Speaking prompt: '{prompt_msg}' (active_convo={is_active_convo})...")
                        speak(prompt_msg)
                        time.sleep(0.05)
                        logger.info("[Wake Word Flow] Prompt finished. Opening microphone to listen for command...")
                    except Exception as e:
                        logger.exception(f"[Wake Word Flow] Error speaking prompt: {e}")
                    
                    text = listen()
                    
            elif trigger_type == "AUTO_SCHEDULED":
                logger.info("=== [Auto Scheduled Triggered] ===")
                print("\n[Auto Scheduled Event!]")
                text = command_text
            
            if text == "error_internet":
                print("Error: Could not connect to the internet.")
                logger.warning("[Main Flow] Speech recognition failed due to internet connection issue.")
                if not internet_warned:
                    try:
                        speak("I am having trouble connecting to the internet.")
                    except Exception as e:
                        logger.exception(f"Error speaking internet warning: {e}")
                    internet_warned = True
                else:
                    logger.info("Internet warning already spoken; suppressing repeated audio warning.")
                continue
            elif text == "error_mic":
                print("Error: Could not access the microphone.")
                logger.error("[Main Flow] Could not access microphone.")
                try:
                    speak("I am having trouble accessing your microphone.")
                except Exception as e:
                    logger.exception(f"Error speaking mic error: {e}")
                continue
            elif text == "error_unknown":
                print("Error: An unexpected error occurred.")
                logger.error("[Main Flow] Unexpected speech recognition error.")
                try:
                    speak("An unexpected error occurred.")
                except Exception as e:
                    logger.exception(f"Error speaking unknown error: {e}")
                continue
            elif text is None:
                logger.info("[Main Flow] listen() returned None (no audio captured above energy threshold or timed out). Returning to idle.")
                print("[I didn't catch that. Back to idle]")
                try:
                    import random
                    fallback_phrases = [
                        "Sorry, I didn't catch that.",
                        "I didn't quite hear you.",
                        "Could you say that again?",
                        "I'm sorry, I didn't understand."
                    ]
                    speak(random.choice(fallback_phrases))
                except Exception as e:
                    logger.exception(f"Error speaking fallback: {e}")
                continue

            # If we reached here, speech recognition succeeded!
            if internet_warned:
                internet_warned = False
                logger.info("Internet connectivity restored for speech recognition.")
                
            logger.info(f"[Main Flow] Received command: '{text}'. Routing to execution...")
            print(f"I heard: '{text}'")
            
            # Execute command and check if shutdown was requested
            last_interaction_time = time.time()
            should_continue = execute_command(text)
            if not should_continue:
                break
                
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Exiting...")
            break
        except Exception as e:
            logger.exception(f"Unexpected error in main loop: {e}")
            print(f"\n[Unexpected Error: {e}. Recovering and resuming in 1s...]")
            time.sleep(1)

    cleanup()

if __name__ == "__main__":
    main()
