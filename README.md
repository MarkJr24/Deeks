# 🎙️ Deeks V2 — Personal AI Voice Assistant

> **Deeks V2** is a fully offline-first, locally-powered personal voice assistant for Windows, built by Mark. It listens for your voice via wake word or hotkey, understands your intent using a hybrid routing engine (fast keyword matching + local LLM), and executes a wide range of commands — from Spotify playback and system media controls to file management, opening apps, checking weather, setting reminders, and managing your schedule — all without sending your personal data to the cloud.

---

## 📋 Table of Contents

- [What's New in V2](#whats-new-in-v2)
- [Concept & Philosophy](#concept--philosophy)
- [Architecture Overview](#architecture-overview)
- [How the Backend Works](#how-the-backend-works)
  - [1. Startup & Initialization](#1-startup--initialization)
  - [2. Trigger System (Wake Word & Hotkey)](#2-trigger-system-wake-word--hotkey)
  - [3. Voice Input Pipeline](#3-voice-input-pipeline)
  - [4. Intent Routing Engine (Hybrid)](#4-intent-routing-engine-hybrid)
  - [5. Skill Execution Layer](#5-skill-execution-layer)
  - [6. Voice Output (TTS)](#6-voice-output-tts)
  - [7. Memory & Persistence](#7-memory--persistence)
  - [8. Background Systems](#8-background-systems)
- [Skills & Capabilities](#skills--capabilities)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Example Commands](#example-commands)

---

## 🚀 What's New in V2

- **🎵 Spotify Web API Skill (`spotify_skill.py`)**: Direct Spotify playback control for playing songs, artists, albums, pausing, resuming, skipping, and going back to previous tracks.
- **⏯️ System Media Controls (`media_control_skill.py`)**: Universal media key simulation (`Play/Pause`, `Next Track`, `Previous Track`) for controlling YouTube, web browsers, and local media players regardless of active application.
- **📁 File Management Skill (`file_management_skill.py`)**:
  - **Open**: Search standard directories (`Desktop`, `Documents`, `Downloads`, `Pictures`) for files/folders and open them in default apps or File Explorer. Interactively asks if multiple matches exist.
  - **Create**: Create new folders on Desktop by default (`"create a folder called [name]"`).
  - **Safe Delete**: Move files/folders to the Windows Recycle Bin using `send2trash` after mandatory spoken voice confirmation (`"Are you sure you want to delete [name]?"`).
  - **Rename**: Rename files/folders with spoken voice confirmation (`"rename [old] to [new]"`).
- **🧠 Enhanced Hybrid Intent Router (`intent_router.py`)**: Expanded system prompt with 29 intent classifications including generic media key controls (`MEDIA_*`) and file management operations (`FILE_*`).

---

## Concept & Philosophy

Deeks is designed around a few core ideas:

| Principle | How It's Implemented |
|---|---|
| **Privacy First** | All LLM inference runs locally via Ollama. No audio, text, or personal data leaves your machine. |
| **Always-On, Low Overhead** | Process priority is set to `BELOW_NORMAL` at startup so Deeks never competes with your work. |
| **Hybrid Speed** | Fast keyword matching handles common commands instantly; the LLM is only invoked as a fallback. |
| **Resilient** | Every component has `try/except` guards and fallback paths (e.g., offline TTS if edge-tts fails). |
| **Safe File Operations** | Destructive actions (deletion) use `send2trash` (Recycle Bin) and require explicit spoken voice confirmation. |
| **Meeting-Aware** | Automatically detects running Zoom/Teams/Webex processes and silences itself completely. |
| **Persistent Memory** | Remembers user facts, preferences, default city, scheduled briefing time, etc. across sessions. |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        TRIGGER LAYER                             │
│  ┌─────────────────┐          ┌──────────────────────────────┐  │
│  │  Hotkey          │          │  Wake Word Listener           │  │
│  │  Ctrl + Alt + D │          │  "Hey Deeks" (background)    │  │
│  └────────┬────────┘          └──────────────┬───────────────┘  │
│           └──────────────┬───────────────────┘                  │
│                          ▼                                       │
│                    trigger_queue                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                     VOICE INPUT LAYER                             │
│   Google Speech Recognition (SpeechRecognition + PyAudio)        │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │ Mic open → Ambient calibration → Listen → Google STT     │   │
│   └──────────────────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────────────────┘
                           │ raw text
┌──────────────────────────▼───────────────────────────────────────┐
│                     INPUT CLEANING LAYER                          │
│   Strips: wake words, "hey deeks", polite prefixes/suffixes       │
└──────────────────────────┬───────────────────────────────────────┘
                           │ clean_text
┌──────────────────────────▼───────────────────────────────────────┐
│                  INTENT ROUTING ENGINE (Hybrid)                   │
│  ┌────────────────────────────────────────────────────┐          │
│  │  PASS 1: Fast keyword/regex matching (inline rules) │          │
│  │  If matched → execute skill directly                │          │
│  └────────────────────────┬───────────────────────────┘          │
│                           │ no match                              │
│  ┌────────────────────────▼───────────────────────────┐          │
│  │  PASS 2: LLM Intent Classification via Ollama       │          │
│  │  Model: phi4-mini (local) | 29 intent labels        │          │
│  │  Returns JSON: {"intent": "...", "params": {...}}    │          │
│  └────────────────────────────────────────────────────┘          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ intent + params
┌──────────────────────────▼───────────────────────────────────────┐
│                    SKILL EXECUTION LAYER                          │
│  spotify / media control / file management / weather / schedule  │
│  reminders / notes / apps / system / power / briefing            │
│  LLM general query (phi4-mini) as final fallback                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │ response text
┌──────────────────────────▼───────────────────────────────────────┐
│                   VOICE OUTPUT LAYER (TTS)                        │
│  edge-tts (Microsoft Neural voices) → pygame playback            │
│  Fallback: pyttsx3 (offline)                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## How the Backend Works

### 1. Startup & Initialization

When Deeks starts (`main.py → main()`), the following sequence runs:

1. **Process priority is lowered** to `BELOW_NORMAL_PRIORITY_CLASS` using `ctypes.windll.kernel32.SetPriorityClass()`, so Deeks never starves foreground apps of CPU.
2. **Status file is written** to `logs/status.json` with PID, start time, and heartbeat info. A `logs/deeks.pid` file is also created for external health checks.
3. **Ollama server is auto-detected and launched** via `ensure_ollama_running()`. It checks `http://localhost:11434/` — if not reachable, it silently spawns `ollama serve` in the background.
4. **Greeting is spoken**: "Hey, I'm online."
5. **Reminder system is initialized**: all saved reminders from `data/reminders.json` are reloaded and scheduled.
6. **Hotkey listener is registered**: `Ctrl+Alt+D` is bound globally using `pynput`.
7. **Background threads start**:
   - Scheduled daily briefing checker (runs every 30 seconds)
   - Wake word listener (Google STT in background, paused during meeting mode)

---

### 2. Trigger System (Wake Word & Hotkey)

Deeks uses a **producer-consumer queue** (`queue.Queue`) as the central coordination mechanism between trigger sources and the main loop.

#### Hotkey — `Ctrl+Alt+D`

- Registered globally using `pynput.keyboard.GlobalHotKeys`.
- A **debounce interval of 1.5 seconds** prevents accidental double-triggers.
- When pressed: pushes `("HOTKEY", None)` into `trigger_queue`.

#### Wake Word — "Hey Deeks"

- Runs in a **background daemon thread** using `recognizer.listen_in_background()` from `SpeechRecognition`.
- Listens with a 5-second phrase time limit for fast turnaround.
- **Wake word variants** are extensively matched to handle mis-transcriptions by Google STT.
- If the wake phrase also contains a command (e.g., "Hey Deeks open Chrome"), the command text is forwarded directly, skipping the second listen step.
- On detection: pushes `("WAKE_WORD", command_text_or_None)` into `trigger_queue`.

---

### 3. Voice Input Pipeline

Once a trigger is received, the **background wake word listener is stopped first** (so the microphone is free), then `listen()` is called from `skills/voice_input.py`.

The `listen()` function follows a **4-stage pipeline**:

| Stage | What Happens |
|---|---|
| **Stage 1 — Mic Open** | Opens `sr.Microphone()` with up to 2 retries |
| **Stage 1 — Calibration** | `adjust_for_ambient_noise(duration=0.1)` — fast ambient noise detection |
| **Stage 2 — Listen** | `recognizer.listen(timeout=8, phrase_time_limit=15)` — waits for speech input |
| **Stage 3 — Audio Captured** | Audio bytes logged |
| **Stage 4 — Google STT** | `recognizer.recognize_google(audio)` — transcribes speech to text |

---

### 4. Intent Routing Engine (Hybrid)

Deeks uses a **two-pass routing strategy** to balance speed and intelligence.

#### Pass 1: Fast Keyword/Regex Matching

Runs first — covers ~80% of real-world commands in O(1) time with zero LLM latency:
- **File Management**: `"open file [name]"`, `"create folder [name]"`, `"delete [name]"`, `"rename [old] to [new]"`
- **Media Controls**: `"play video"`, `"pause video"`, `"pause the music"`, `"skip"`, `"next"`, `"previous"`, `"go back"`
- **Spotify**: `"play [song] on spotify"`, `"pause spotify"`, `"next song on spotify"`
- **Volume**: `"volume"`, `"louder"`, `"mute"`
- **Lock PC / Screenshot / Power**: `"lock pc"`, `"take a screenshot"`, `"shutdown"`
- **Weather / Schedule / Reminders / Timer / News / Briefing / Notes / Memory**

#### Pass 2: LLM Intent Classification (Fallback)

If **no keyword rule matches**, `classify_intent(clean_text)` calls local `phi4-mini` via Ollama:
- Outputs JSON intent: `{"intent": "FILE_OPEN", "params": {"target_name": "ProjectReport"}}`
- System prompt defines **29 valid intent labels**.

| Intent | Description |
|---|---|
| `EXIT` | Shut down Deeks |
| `SHUTDOWN_PC` / `RESTART_PC` / `LOCK_PC` | PC power controls |
| `SCREENSHOT` | Take a screenshot |
| `MEETING_MODE_ON` / `MEETING_MODE_OFF` | Toggle meeting mode |
| `VOLUME_ADJUST` | Change system volume |
| `BRIEFING` / `BRIEFING_SCHEDULE` | Daily briefing |
| `WEATHER` | Fetch weather with optional city param |
| `SCHEDULE_GET` / `SCHEDULE_ADD` / `SCHEDULE_CLEAR` | Calendar management |
| `NEWS` | Fetch top headlines |
| `SEARCH` | Web search with query param |
| `REMINDER` | Set/cancel reminders |
| `TIMER` | Set a countdown timer |
| `CLIPBOARD_READ` | Read clipboard text |
| `NOTES_SAVE` / `NOTES_READ` / `NOTES_CLEAR` | Note management |
| `MEMORY_SAVE` / `MEMORY_READ` | Persistent user facts |
| `TIME` | Current time |
| `OPEN_APP` / `CLOSE_APP` | Launch/close applications |
| `OPEN_WEBSITE` | Open a website |
| `SPOTIFY_PLAY` / `SPOTIFY_PAUSE` / `SPOTIFY_RESUME` / `SPOTIFY_NEXT` / `SPOTIFY_PREVIOUS` | Spotify Web API control |
| `MEDIA_PLAY_PAUSE` / `MEDIA_NEXT` / `MEDIA_PREVIOUS` | Universal system media key controls |
| `FILE_OPEN` / `FILE_CREATE_FOLDER` / `FILE_DELETE` / `FILE_RENAME` | File & folder management |
| `GENERAL_QUERY` | Free-form conversation via Ollama |

---

### 5. Skill Execution Layer

Each capability is encapsulated under `skills/`:

#### File Management (`skills/file_management_skill.py`)
- Searches common directories (`Desktop`, `Documents`, `Downloads`, `Pictures`).
- **Open**: Opens files/folders via `os.startfile`. Asks for clarification if multiple matches exist.
- **Create**: Creates new folders (`os.makedirs`) on Desktop by default.
- **Delete**: Moves items to Windows Recycle Bin via `send2trash` after explicit voice confirmation (`"Are you sure you want to delete [name]?"`).
- **Rename**: Renames items via `os.rename` after explicit voice confirmation.

#### System Media Controls (`skills/media_control_skill.py`)
- Simulates hardware media keys (`Play/Pause`, `Next Track`, `Previous Track`) using `pynput` (with `pyautogui` fallback).
- Controls YouTube videos, web audio, Spotify, and local players universally.

#### Spotify Integration (`skills/spotify_skill.py`)
- Controls Spotify playback via `spotipy` and Spotify Web API OAuth tokens.

#### Weather (`skills/weather_skill.py`)
- Free [Open-Meteo API](https://open-meteo.com) integration with geocoding and natural weather descriptions.

#### Schedule (`skills/schedule_skill.py`)
- Calendar events stored in `memory/schedule.json` with natural language date parsing.

#### Reminders (`skills/reminders.py`)
- Persistent schedule in `data/reminders.json` supporting one-time and recurring daily reminders.

#### Clipboard & Notes (`skills/clipboard_notes.py`)
- System clipboard access via `pyperclip` and note persistence in `data/notes.json`.

#### App & Web Launcher (`skills/open_app_skill.py`, `skills/web_actions.py`)
- Launch/close Windows apps (with registry search fallback) and open web search/sites in default browser.

#### System & Power (`skills/system_utils.py`, `skills/power_control.py`)
- Workstation lock, screenshot capture, meeting app detection, shutdown/restart with confirmation.

#### Volume Control (`skills/volume_control.py`)
- Windows Core Audio API (`pycaw`) control for system master volume and mute state.

#### LLM General Query (`skills/llm_skill.py`)
- Conversational fallback using `phi4-mini` via Ollama with user memory facts context injection.

---

### 6. Voice Output (TTS)

Managed by `skills/voice_output.py`:
- **Primary**: `edge-tts` (Microsoft Neural voices, default: `en-US-AriaNeural`, playback via `pygame.mixer`).
- **Fallback**: `pyttsx3` (offline Windows SAPI).
- **Meeting Mode**: Mutes output during detected video meetings.

---

### 7. Memory & Persistence

Managed by `memory/memory.py` backed by `memory/data.json`:
- Stores default city, daily briefing time, meeting mode state, and persistent user facts.

---

## Skills & Capabilities Summary

| Category | Supported Voice Commands |
|---|---|
| **File Management** | "Open file report.pdf", "Create a folder called Projects", "Delete folder Drafts", "Rename old.txt to new.txt" |
| **Media Keys** | "Play video", "Pause video", "Pause the music", "Skip", "Next", "Go back", "Previous" |
| **Spotify** | "Play Blinding Lights on Spotify", "Pause Spotify", "Resume Spotify", "Next track on Spotify" |
| **Time & Weather** | "What's the time?", "What's the weather in London?" |
| **Schedule** | "What's on my schedule?", "Add team meeting tomorrow at 3pm", "Clear schedule" |
| **Reminders** | "Remind me to take medicine in 30 minutes", "Remind me every day to drink water at 8am" |
| **Timer** | "Set a timer for 5 minutes" |
| **News & Briefing** | "What's the latest news?", "Give me my daily briefing" |
| **Apps & Websites** | "Open VS Code", "Close Discord", "Open YouTube", "Open GitHub" |
| **Volume** | "Turn up the volume", "Mute", "Set volume to 50%" |
| **Search & Notes** | "Google Python tutorials", "Make a note: buy milk", "Read my notes", "Read my clipboard" |
| **Memory & System** | "Remember that I prefer dark mode", "Take a screenshot", "Lock my PC", "Shutdown the PC" |
| **General AI** | Any general question or conversation |

---

## Tech Stack

- **Core**: Python 3.10+
- **Voice Input (STT)**: `SpeechRecognition`, `PyAudio`, Google Speech-to-Text API
- **AI / LLM**: Ollama, `phi4-mini` local model (3.8B parameters)
- **Voice Output (TTS)**: `edge-tts` (Microsoft Neural Voices), `pygame`, `pyttsx3` fallback
- **File Management & System**: `send2trash`, `pynput`, `pycaw`, `ctypes`, `winreg`, `pyperclip`, `PIL (Pillow)`
- **Spotify**: `spotipy` (Spotify Web API)
- **Scheduling**: `schedule`, `threading`, `queue`, `uuid`

---

## Project Structure

```
Deeks/
├── main.py                    # Core orchestrator: trigger loop, intent routing, command dispatch
├── logger.py                  # Centralized logger setup
├── status.py                  # Standalone health status monitoring tool
├── run_deeks.bat              # Windows launch script
├── start_deeks.vbs            # Silent VBS launcher
├── requirements.txt           # Python dependencies
├── test_resilience.py         # Integration and resilience test suite
│
├── skills/                    # Modular skill implementations
│   ├── file_management_skill.py # Open, create, trash (send2trash), rename files/folders
│   ├── media_control_skill.py   # Universal system media key simulation (Play/Pause, Next, Prev)
│   ├── spotify_skill.py       # Spotify Web API playback control
│   ├── intent_router.py       # Hybrid LLM intent classification (phi4-mini via Ollama)
│   ├── voice_input.py         # Mic input + Google STT + wake word listener
│   ├── voice_output.py        # edge-tts neural TTS + pygame playback + pyttsx3 fallback
│   ├── llm_skill.py           # General Q&A via local Ollama (phi4-mini)
│   ├── weather_skill.py       # Open-Meteo weather API integration
│   ├── schedule_skill.py      # Calendar/schedule management
│   ├── reminders.py           # Persistent reminder system with scheduling
│   ├── news_skill.py          # Top headlines fetching
│   ├── briefing_skill.py      # Daily briefing compilation
│   ├── open_app_skill.py      # App launch/close + Windows Registry lookup
│   ├── web_actions.py         # Google web search & website opening
│   ├── volume_control.py      # Windows audio volume via pycaw
│   ├── system_utils.py        # Lock PC, screenshot, Ollama health, meeting detection
│   ├── power_control.py       # Shutdown/restart with voice confirmation
│   ├── clipboard_notes.py     # Clipboard reading + notes save/read/clear
│   ├── search_skill.py        # Google web search opener
│   ├── time_skill.py          # Current time retrieval
│   └── timer_skill.py         # Countdown timer
│
├── memory/                    # Persistent K/V memory & calendar data
├── data/                      # Persistent reminders & notes storage
├── logs/                      # Status heartbeat & logs
└── screenshots/               # Auto-saved screenshots
```

---

## Installation & Usage

```bash
# Clone the repo
git clone https://github.com/MarkJr24/Deeks.git
cd Deeks

# Create virtual environment and activate
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Deeks
python main.py
# Or run via batch file
run_deeks.bat
```

---

*Built with love by Mark — a personal assistant that respects your privacy.*
