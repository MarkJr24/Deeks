<div align="center">

# 🤖 Deeks — Personal Voice Assistant

**A fully offline-capable, AI-powered personal voice assistant for Windows.**  
Deeks understands natural speech, runs entirely on your local machine, and handles everything from locking your PC to reading the news.

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20phi4--mini-purple)](https://ollama.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Running Deeks](#-running-deeks)
- [Voice Commands](#-voice-commands)
- [NLP Intent Routing](#-nlp-intent-routing)
- [Configuration](#-configuration)
- [Data & Privacy](#-data--privacy)
- [Git & Version Control](#-git--version-control)
- [Troubleshooting](#-troubleshooting)

---

## 🌟 Overview

Deeks is a **Python-based voice assistant** that listens for a wake word (`Hey Deeks`), understands what you say using Google's Speech Recognition, and routes your command intelligently using a **Hybrid NLP Intent Router**:

1. **Fast Keyword Pass** — instant 0ms execution for common commands.
2. **AI Intent Fallback** — if your phrasing doesn't match keywords, it uses a local LLM (Ollama `phi4-mini`) to understand what you meant and route accordingly.

Deeks is fully **offline-first** — weather, reminders, timers, app control, system actions, notes, and clipboard all work without an internet connection. Only weather, news, and speech recognition require internet.

---

## ✨ Features

| Category | Capability |
|---|---|
| 🎙️ Voice Input | Wake word detection, Google STT, low-latency listening |
| 🔊 Voice Output | Microsoft Edge Neural TTS (`en-US-AriaNeural` by default) |
| 🧠 NLP Routing | Hybrid keyword + Ollama LLM intent classifier |
| 🌦️ Weather | Real-time weather via Open-Meteo (free, no API key) |
| 📰 News | Top headlines via BBC & Google News RSS feeds |
| ⏰ Reminders | One-time & daily recurring reminders with custom messages |
| ⏱️ Timer | Set voice-activated timers with spoken alert when done |
| 📋 Clipboard | Read clipboard content out loud |
| 📝 Notes | Save, read back, and clear personal notes |
| 🗓️ Schedule | Add and view calendar events |
| 📢 Daily Briefing | Morning summary of weather, news, and schedule |
| 🔊 Volume Control | Increase, decrease, mute/unmute system volume |
| 🔒 System Control | Lock PC, take screenshot, shutdown, restart |
| 📱 App Control | Open and close applications by voice |
| 🔍 Web Search | Open Google search from voice command |
| 💬 Meeting Mode | Silences Deeks during video calls |
| 🧠 Memory | Remembers facts about you across sessions |
| 📡 Status Monitor | Real-time status dashboard (`status.py`) |

---

## 🛠️ Tech Stack

### Core Language
- **Python 3.13** — main runtime

### Voice I/O
| Library | Purpose |
|---|---|
| `SpeechRecognition` | Google STT — converts spoken audio to text |
| `PyAudio` | Microphone audio capture |
| `edge-tts` | Microsoft Edge Neural TTS — natural voice output |
| `pygame` | Audio playback engine for TTS output |
| `pynput` | Global hotkey listener (`Ctrl+Alt+D`) |

### AI / NLP
| Library | Purpose |
|---|---|
| `ollama` | Local LLM integration — runs `phi4-mini` model for intent classification and general conversation |

### System Integration
| Library | Purpose |
|---|---|
| `pycaw` | Windows audio/volume control via COM |
| `pyperclip` | Cross-platform clipboard read/write |
| `ctypes` | Win32 API calls (lock screen, process priority) |
| `subprocess` | App launching and system commands |

### Scheduling & Data
| Library | Purpose |
|---|---|
| `schedule` | Background reminder scheduler (runs in its own thread) |
| `json` | Persistent storage for notes, reminders, memory, schedule |

### External APIs (Free, No Key Required)
| API | Purpose |
|---|---|
| [Open-Meteo](https://open-meteo.com/) | Real-time weather data by city |
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | City name → lat/lon coordinates |
| [BBC News RSS](https://feeds.bbci.co.uk/news/rss.xml) | Top news headlines |
| [Google News RSS](https://news.google.com/rss) | Additional news headlines |

---

## 📁 Project Structure

```
Deeks/
│
├── main.py                   # Main entry point — conversation loop & command routing
├── logger.py                 # Centralized logging setup
├── status.py                 # Real-time status dashboard
├── requirements.txt          # Python package dependencies
├── run_deeks.bat             # Double-click launcher for Windows
├── start_deeks.vbs           # Silent background launcher (no console window)
├── start_deeks_startup.vbs   # Windows Startup folder auto-launch script
├── startup.ps1               # PowerShell startup helper
├── poll_ollama.ps1           # Ensures Ollama is running before Deeks starts
│
├── skills/                   # All skill modules (one file per capability)
│   ├── intent_router.py      # 🆕 Hybrid NLP intent classifier (Ollama-powered)
│   ├── voice_input.py        # Microphone listening + wake word detection
│   ├── voice_output.py       # Edge TTS text-to-speech engine
│   ├── llm_skill.py          # General conversation handler (Ollama phi4-mini)
│   ├── weather_skill.py      # Open-Meteo weather queries
│   ├── news_skill.py         # BBC/Google News RSS reader
│   ├── briefing_skill.py     # Daily morning briefing generator
│   ├── schedule_skill.py     # Calendar events add/view
│   ├── reminders.py          # One-time & recurring daily reminders
│   ├── timer_skill.py        # Countdown timer with audio alert
│   ├── clipboard_notes.py    # Clipboard reader + personal notes
│   ├── open_app_skill.py     # App launch and close by name
│   ├── search_skill.py       # Opens Google search in browser
│   ├── time_skill.py         # Returns current time
│   ├── volume_control.py     # Windows volume up/down/mute via pycaw
│   ├── system_utils.py       # Lock PC, take screenshot
│   └── power_control.py      # Shutdown and restart PC
│
├── memory/
│   ├── memory.py             # Key-value persistent memory (JSON)
│   ├── data.json             # Stored user facts & preferences (gitignored)
│   └── schedule.json         # Calendar events store (gitignored)
│
├── data/
│   ├── notes.json            # Saved notes (gitignored)
│   └── reminders.json        # Active reminders (gitignored)
│
└── logs/
    ├── deeks.log             # Runtime logs (gitignored)
    ├── status.json           # Live status (gitignored)
    └── deeks.pid             # Process ID file (gitignored)
```

---

## ✅ Prerequisites

Before installing Deeks, make sure you have:

1. **Python 3.10+** — [Download here](https://www.python.org/downloads/)
2. **Ollama** — [Download here](https://ollama.com/download)
3. **Microsoft Visual C++ Build Tools** — required for `PyAudio`
4. A working **microphone**
5. **Windows 10 or 11**

### Install Ollama phi4-mini model
After installing Ollama, pull the model Deeks uses:
```powershell
ollama pull phi4-mini
```

Verify it works:
```powershell
ollama run phi4-mini "Say hello"
```

---

## 🚀 Installation

### Step 1 — Clone the Repository
```powershell
git clone https://github.com/MarkJr24/Deeks.git
cd Deeks
```

### Step 2 — Create a Virtual Environment
```powershell
python -m venv venv
```

### Step 3 — Activate the Virtual Environment
```powershell
venv\Scripts\activate
```

### Step 4 — Install Dependencies
```powershell
pip install -r requirements.txt
```

> **Note:** If `PyAudio` fails to install, install it manually:
> ```powershell
> pip install pipwin
> pipwin install pyaudio
> ```

### Step 5 — Verify Ollama is Running
```powershell
ollama serve
```
Or check if it's already running:
```powershell
curl http://localhost:11434
```

---

## ▶️ Running Deeks

### Option 1 — Direct Python (Recommended for Development)
```powershell
venv\Scripts\python.exe main.py
```

### Option 2 — Double-click Launcher
Just double-click `run_deeks.bat` in File Explorer.

### Option 3 — Silent Background Launch (No Console Window)
```powershell
wscript.exe start_deeks.vbs
```

### Option 4 — Auto-start with Windows
Copy `start_deeks_startup.vbs` into your Windows Startup folder:
```
Win + R → shell:startup → paste start_deeks_startup.vbs here
```

### Check Status
While Deeks is running, open a second terminal and run:
```powershell
venv\Scripts\python.exe status.py
```

---

## 🎙️ Voice Commands

> 💡 **Tip**: You no longer need exact phrases! Deeks understands natural speech.
> For example, *"Deeks, could you lock up my machine?"* works just as well as *"lock pc"*.

### 🔴 System Control
| What you say | Action |
|---|---|
| `"goodbye"` / `"exit"` / `"close Deeks"` | Shuts down Deeks |
| `"lock my pc"` / `"lock the screen"` | Locks Windows workstation |
| `"shut down the computer"` | Shuts down PC (asks for confirmation) |
| `"restart"` / `"reboot"` | Restarts PC (asks for confirmation) |
| `"take a screenshot"` | Captures and saves screenshot |

### 🔊 Volume
| What you say | Action |
|---|---|
| `"turn up the volume"` / `"louder"` | Increases volume |
| `"turn down the volume"` / `"quieter"` | Decreases volume |
| `"mute"` / `"unmute"` | Toggles mute |

### 🌦️ Weather
| What you say | Action |
|---|---|
| `"what's the weather?"` | Weather for your default city |
| `"weather in London"` | Weather for a specific city |
| `"is it going to rain today?"` | Checks your city's rain forecast |

### 📰 News
| What you say | Action |
|---|---|
| `"what's the news?"` | Reads top 5 headlines |
| `"give me the headlines"` | Same as above |

### ⏰ Reminders
| What you say | Action |
|---|---|
| `"remind me to drink water in 30 minutes"` | One-time reminder in 30 mins |
| `"remind me to call mom at 5 pm"` | One-time reminder at a specific time |
| `"remind me every day to take my vitamins at 8 am"` | Daily recurring reminder |
| `"cancel my reminders"` | Clears all active reminders |

### ⏱️ Timer
| What you say | Action |
|---|---|
| `"set a timer for 5 minutes"` | Starts a 5-minute countdown |
| `"set a timer for ten minutes"` | Supports word numbers too |

### 📋 Clipboard & Notes
| What you say | Action |
|---|---|
| `"read clipboard"` | Reads current clipboard text aloud |
| `"remember this: [note text]"` | Saves a note |
| `"make a note: [note text]"` | Same as above |
| `"read my notes"` | Reads all saved notes aloud |
| `"clear my notes"` | Deletes all saved notes |

### 🗓️ Schedule
| What you say | Action |
|---|---|
| `"what's on my schedule?"` | Today's events |
| `"what's on my schedule tomorrow?"` | Tomorrow's events |
| `"add an event: team meeting at 3 pm"` | Adds event to calendar |

### 📢 Daily Briefing
| What you say | Action |
|---|---|
| `"brief me"` / `"give me a briefing"` | Weather + news + today's schedule |
| `"schedule briefing at 8 am"` | Sets daily briefing time |

### 🔍 Search & Info
| What you say | Action |
|---|---|
| `"search for Python tutorials"` | Opens Google search |
| `"what is the speed of light?"` | Searches and opens results |

### 📱 App Control
| What you say | Action |
|---|---|
| `"open Chrome"` / `"launch Notepad"` | Opens the app |
| `"close Chrome"` / `"quit Notepad"` | Closes the app |

### 💬 Meeting Mode
| What you say | Action |
|---|---|
| `"enable meeting mode"` / `"mute Deeks"` | Deeks goes silent |
| `"disable meeting mode"` / `"unmute Deeks"` | Deeks comes back online |

### 🧠 Memory
| What you say | Action |
|---|---|
| `"remember that my office is on the 3rd floor"` | Saves a persistent fact |
| `"what did I tell you to remember?"` | Recalls last saved fact |

### ⌚ Time
| What you say | Action |
|---|---|
| `"what time is it?"` | Speaks current time |

---

## 🧠 NLP Intent Routing

Deeks uses a **two-layer routing system**:

### Layer 1: Fast Keyword Match (0ms)
Common phrases are checked instantly against keyword patterns in `main.py`. If matched, the skill executes immediately — no AI overhead.

### Layer 2: LLM Intent Classifier (via Ollama, ~0.5-1s)
If Layer 1 doesn't match, `skills/intent_router.py` sends the text to local `phi4-mini` with a structured system prompt listing all 26+ intents. Ollama returns a JSON object:

```json
{"intent": "WEATHER", "params": {"city": "Chennai"}}
```

`main.py` then dispatches to the correct skill based on the classified intent.

**Supported Intent Labels:**
`EXIT`, `SHUTDOWN_PC`, `RESTART_PC`, `LOCK_PC`, `SCREENSHOT`, `MEETING_MODE_ON`, `MEETING_MODE_OFF`, `VOLUME_ADJUST`, `BRIEFING`, `BRIEFING_SCHEDULE`, `WEATHER`, `SCHEDULE_GET`, `SCHEDULE_ADD`, `NEWS`, `SEARCH`, `REMINDER`, `TIMER`, `CLIPBOARD_READ`, `NOTES_SAVE`, `NOTES_READ`, `NOTES_CLEAR`, `MEMORY_SAVE`, `MEMORY_READ`, `TIME`, `OPEN_APP`, `CLOSE_APP`, `GENERAL_QUERY`

---

## ⚙️ Configuration

### Change Default City for Weather
Say: *"What's the weather in Mumbai?"* — Deeks will remember Mumbai as your default city.

Or edit `memory/data.json` directly:
```json
{"default_city": "Mumbai"}
```

### Change TTS Voice
Set the environment variable before running:
```powershell
$env:DEEKS_VOICE = "en-US-JennyNeural"
python main.py
```

**Available voices:**
| Key | Voice ID | Style |
|---|---|---|
| `aria` | `en-US-AriaNeural` | Natural expressive (Default) |
| `jenny` | `en-US-JennyNeural` | Warm, conversational |
| `guy` | `en-US-GuyNeural` | Professional male |
| `sonia` | `en-GB-SoniaNeural` | British English female |
| `ryan` | `en-GB-RyanNeural` | British English male |

### Change Ollama Model
Edit `skills/llm_skill.py` and `skills/intent_router.py`:
```python
response = ollama.chat(model='llama3.2', ...)  # Change model name here
```

---

## 🔒 Data & Privacy

All personal data is stored **locally** on your machine and is **never sent to any external server**:

| File | Contents | Gitignored? |
|---|---|---|
| `memory/data.json` | User facts, preferences, default city | ✅ Yes |
| `memory/schedule.json` | Calendar events | ✅ Yes |
| `data/notes.json` | Personal notes | ✅ Yes |
| `data/reminders.json` | Active reminders | ✅ Yes |
| `logs/` | Runtime logs | ✅ Yes |

> ⚠️ **Note:** Speech recognition uses Google's online STT API. Your voice is processed by Google's servers momentarily for transcription. Everything else is fully local.

---

## 🔧 Git & Version Control

### View Commit History
```powershell
git log --oneline
```

### Revert to a Previous Version
```powershell
# See the commit ID you want to go back to
git log --oneline

# Reset to that commit (replaces all files with that snapshot)
git reset --hard <commit-id>
```

### Create a New Branch for Experiments
```powershell
git checkout -b feature/my-new-skill
```

### Push Changes to GitHub
```powershell
git add .
git commit -m "Add new skill: [description]"
git push origin main
```

### Pull Latest Changes
```powershell
git pull origin main
```

---

## 🐛 Troubleshooting

### Deeks doesn't respond to voice
- Check microphone is set as default input in Windows Sound Settings.
- Make sure internet is available (Google STT requires it).
- Try running: `venv\Scripts\python.exe -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"`

### Ollama errors / intent classification fails
- Make sure Ollama is running: `ollama serve`
- Verify model is installed: `ollama list`
- Pull the model if missing: `ollama pull phi4-mini`

### PyAudio installation fails
```powershell
pip install pipwin
pipwin install pyaudio
```

### No sound / TTS not working
- Check `pygame` and `edge-tts` are installed: `pip install pygame edge-tts`
- Confirm your default audio output device is set correctly in Windows.

### Lock PC command not working
- Deeks uses `ctypes.windll.user32.LockWorkStation()` with a `rundll32.exe` fallback.
- Make sure you're running Deeks with your user account (not as Administrator).

---

## 👨‍💻 Author

**Mark Jr** — [@MarkJr24](https://github.com/MarkJr24)

---

<div align="center">

*Built with 🖤 — fully local, fully personal, fully yours.*

</div>
