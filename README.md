# Deeks - Personal Voice Assistant

Deeks is a Python-based personal voice assistant designed to handle local interactions seamlessly. It uses a lightweight, completely offline wake word engine and features several extensible "skills."

## Prerequisites
- Python 3.11+
- Windows OS (relies on Windows native TTS and 'start' commands)

## Setup and Installation

1. **Create and Activate a Virtual Environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Run the Assistant:**
   - **Interactive Terminal:**
     ```powershell
     .\venv\Scripts\python.exe main.py
     ```
   - **Silent Background Process:**
     ```powershell
     wscript start_deeks.vbs
     ```

## Checking Status & Management

You can check if Deeks is currently running directly from the terminal:

```powershell
.\venv\Scripts\python.exe status.py
```

Options:
- `.\venv\Scripts\python.exe status.py` : Displays whether Deeks is running, PID, uptime, heartbeat, and recent logs.
- `.\venv\Scripts\python.exe status.py --tail 15` : Shows the last 15 log lines.
- `.\venv\Scripts\python.exe status.py --stop` : Gracefully terminates the running Deeks process.

## Architecture & Resilience Features

* **Text-to-Speech (TTS):** Uses pyttsx3 for completely offline, fast, and free voice generation using native Windows voices.
* **Speech Recognition Resilience:** Uses SpeechRecognition with automatic retry logic for transient network failures. If internet connectivity drops, Deeks speaks a single warning once (suppressing repetitive audio alerts) and silently waits until internet is restored.
* **Offline Wake Word & Hotkey:** Deeks responds immediately when triggered via the **Ctrl+Alt+D** global push-to-talk hotkey or offline wake word.
* **Fault-Tolerant Logging:** All errors and events are automatically captured in `logs/deeks.log` using a rotating file logger (up to 5MB with backups). Unexpected exceptions in skill execution or the main loop are caught and logged without crashing the background daemon.
* **Status & Heartbeat Tracking:** Maintains live PID and timestamped heartbeats in `logs/status.json` and `logs/deeks.pid` for instant status monitoring.

## Available Skills

Deeks features a modular skill system located in the `/skills/` and `/memory/` directories:

### 1. Memory (`memory.py`)
- **Commands:** *"Remember [something]"* | *"What did I tell you to remember?"*
- **Function:** Saves the specified phrase to a local `data.json` file, ensuring its memory persists even if you restart the application.

### 2. Time (`time_skill.py`)
- **Command:** *"What time is it?"*
- **Function:** Checks the system clock and reads the current local time out loud.

### 3. Web Search (`search_skill.py`)
- **Commands:** *"Search for [query]"* | *"What is [query]"*
- **Function:** Automatically opens your default web browser and loads the Google search results for your query.

### 4. Background Timer (`timer_skill.py`)
- **Command:** *"Set a timer for [X] minutes"*
- **Function:** Spawns a background thread that counts down the specified time before announcing *"Time is up!"*. Because it runs in the background, you can continue to use other Deeks commands while the timer ticks down.

### 5. App Launcher (`open_app_skill.py`)
- **Command:** *"Open [App Name]"*
- **Function:** Launches local Windows applications instantly. Currently configured to support Notepad, Calculator, and Chrome.

### 6. Weather Forecast (`weather_skill.py`)
- **Commands:** *"What's the weather?"* | *"What's the weather like?"* | *"What's the weather in [City]?"*
- **Function:** Fetches current temperature, weather conditions, and precipitation probability via the free Open-Meteo API. Remembers your default city in local memory so you only need to set it once.

### 7. Schedule & Agenda (`schedule_skill.py`)
- **Commands:** *"Add an event tomorrow at 3pm dentist appointment"* | *"What's on my schedule today?"* | *"What's on my schedule tomorrow?"*
- **Function:** Parses natural date, time, and event description, saving them chronologically to `memory/schedule.json`. Reads back your scheduled events cleanly in order.

### 8. News Headlines (`news_skill.py`)
- **Commands:** *"What's the news?"* | *"Give me the headlines"* | *"What are the top headlines?"*
- **Function:** Fetches current top news headlines from trusted free RSS feeds (BBC News / Google News) and reads them aloud as concise, spoken sentences.

### 9. Daily Briefing (`briefing_skill.py`)
- **Commands:** *"Give me my daily briefing"* | *"Brief me"*
- **Function:** Assembles a fluid, all-in-one spoken update: time-of-day greeting &rarr; current weather &rarr; today's schedule &rarr; top 3 news headlines &rarr; closing sign-off. Crafted to be concise and finish in under 30 seconds.

## Closing the Assistant
- **Via Voice:** Wait for the prompt and say **"Stop"**, **"Goodbye"**, or **"Shut down"**.
- **Via Terminal:** Run `.\venv\Scripts\python.exe status.py --stop`
