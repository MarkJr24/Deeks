import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
STATUS_FILE = os.path.join(LOG_DIR, "status.json")
PID_FILE = os.path.join(LOG_DIR, "deeks.pid")
LOG_FILE = os.path.join(LOG_DIR, "deeks.log")

def is_pid_running(pid: int) -> bool:
    """Checks if a process with given PID is currently running."""
    if pid <= 0:
        return False
    # Windows-specific process check via tasklist or ctypes
    try:
        if sys.platform == "win32":
            output = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                text=True,
                stderr=subprocess.DEVNULL
            )
            return str(pid) in output
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def get_status():
    """Reads status file and verifies process state."""
    status_data = {}
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except Exception:
            pass

    pid = status_data.get("pid")
    if not pid and os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
                status_data["pid"] = pid
        except Exception:
            pass

    # Process is only considered running if its recorded state is "running" AND the PID is actually active on the system
    if status_data.get("status") == "running" and pid and is_pid_running(pid):
        status_data["is_running"] = True
    else:
        status_data["is_running"] = False

    return status_data

def format_uptime(start_timestamp):
    if not start_timestamp:
        return "Unknown"
    try:
        start_time = datetime.fromisoformat(start_timestamp)
        delta = datetime.now() - start_time
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "Unknown"

def tail_log(lines=10):
    """Returns the last N lines from the log file."""
    if not os.path.exists(LOG_FILE):
        return ["(No log file found at logs/deeks.log)"]
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return [line.rstrip() for line in all_lines[-lines:]]
    except Exception as e:
        return [f"(Error reading log file: {e})"]

def print_status(tail_count=5):
    status = get_status()
    running = status.get("is_running", False)
    
    print("=" * 60)
    print("                DEEKS ASSISTANT STATUS")
    print("=" * 60)
    
    if running:
        pid = status.get("pid", "Unknown")
        started = status.get("start_time", "Unknown")
        uptime = format_uptime(started)
        last_heartbeat = status.get("last_heartbeat", "Unknown")
        hotkey = status.get("hotkey", "Ctrl+Alt+D")
        
        print(f" Status:           [ RUNNING ]")
        print(f" Process ID (PID): {pid}")
        print(f" Started At:       {started}")
        print(f" Uptime:           {uptime}")
        print(f" Last Heartbeat:   {last_heartbeat}")
        print(f" Activation:       {hotkey} (or 'Hey Deeks')")
        print(f" Log File:         {LOG_FILE}")
    else:
        print(f" Status:           [ STOPPED ]")
        print(f" Log File:         {LOG_FILE}")
        print("-" * 60)
        print(" How to Start Deeks:")
        print("   - In Background:  wscript start_deeks.vbs")
        print("   - In Terminal:    .\\venv\\Scripts\\python.exe main.py")
        
    print("-" * 60)
    print(f" Recent Log Entries ({tail_count} lines):")
    recent_logs = tail_log(tail_count)
    if recent_logs:
        for line in recent_logs:
            print(f"   {line}")
    else:
        print("   (No logs yet)")
    print("=" * 60)

def stop_deeks():
    status = get_status()
    if not status.get("is_running", False):
        print("Deeks is not currently running.")
        return
        
    pid = status.get("pid")
    print(f"Stopping Deeks (PID: {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)
        print("Deeks has been stopped successfully.")
    except Exception as e:
        print(f"Error stopping Deeks: {e}")

def main():
    parser = argparse.ArgumentParser(description="Deeks Voice Assistant Status & Management")
    parser.add_argument("--tail", "-t", type=int, default=5, help="Number of recent log lines to display (default: 5)")
    parser.add_argument("--stop", action="store_true", help="Stop the running Deeks instance")
    
    args = parser.parse_args()
    
    if args.stop:
        stop_deeks()
    else:
        print_status(tail_count=args.tail)

if __name__ == "__main__":
    main()
