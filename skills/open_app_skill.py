import os
import sys
import re
import subprocess
import winreg
from logger import logger

# Common Windows app name aliases and direct paths
_KNOWN_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "word pad": "wordpad.exe",
    "wordpad": "wordpad.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "snipping tool": "snippingtool.exe",
    "clock": "ms-clock:",
    "calendar": "outlookcal:",
    "store": "ms-windows-store:",
    "photos": "ms-photos:",
    "mail": "outlookmail:",
    "maps": "bingmaps:",
    "camera": "microsoft.windows.camera:",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "google chrome browser": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "msedge": "msedge.exe",
    "brave": "brave.exe",
    "brave browser": "brave.exe",
    "firefox": "firefox.exe",
    "mozilla firefox": "firefox.exe",
    "vscode": "code.cmd",
    "vs code": "code.cmd",
    "code": "code.cmd",
    "visual studio code": "code.cmd",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "slack": "slack.exe",
    "steam": "steam.exe",
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "vlc media player": "vlc.exe",
    "word": "winword.exe",
    "ms word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "ms excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "ms powerpoint": "powerpnt.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
}

# Well-known browsers and sites that open in browser
_WEB_APPS = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "netflix": "https://netflix.com",
    "spotify": "https://open.spotify.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "instagram": "https://instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "github": "https://github.com",
    "reddit": "https://reddit.com",
    "linkedin": "https://linkedin.com",
    "facebook": "https://facebook.com",
}


def _find_app_in_registry(app_name):
    """Search the Windows registry App Paths for an installed application."""
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
    ]
    search_names = [
        f"{app_name}.exe",
        f"{app_name.replace(' ', '')}.exe",
        f"{app_name.replace(' ', '-')}.exe",
    ]
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for reg_path in reg_paths:
            for exe_name in search_names:
                try:
                    key_path = f"{reg_path}\\{exe_name}"
                    key = winreg.OpenKey(hive, key_path)
                    path, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    if path and os.path.exists(path):
                        return path
                except Exception:
                    continue
    return None


def _find_app_in_common_dirs(app_name):
    """Search common installation directories for an .exe matching the app name."""
    search_dirs = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("APPDATA", ""),
        r"C:\Program Files\WindowsApps",
    ]
    # Clean up app name for directory/file matching
    clean = app_name.lower().replace(" ", "")
    clean_spaced = app_name.lower()

    for base_dir in search_dirs:
        if not base_dir or not os.path.isdir(base_dir):
            continue
        try:
            for root, dirs, files in os.walk(base_dir):
                # Don't go too deep, keep it snappy
                depth = root.replace(base_dir, "").count(os.sep)
                if depth > 3:
                    dirs[:] = []
                    continue
                for fname in files:
                    fname_lower = fname.lower()
                    if fname_lower.endswith(".exe"):
                        basename = fname_lower[:-4]
                        if basename == clean or basename == clean_spaced or clean in basename:
                            return os.path.join(root, fname)
        except (PermissionError, OSError):
            continue
    return None


def is_known_app(app_name: str) -> bool:
    """Checks whether the application name matches a known alias or web app."""
    if not app_name:
        return False
    clean = app_name.lower().strip().strip('"\'.')
    clean = re.sub(r'^(?:the|a|an)\s+', '', clean)
    clean = re.sub(r'\s+(?:app|application|program)$', '', clean)
    return clean in _KNOWN_APPS or clean in _WEB_APPS


def open_application(app_name: str) -> bool:
    """
    Opens an application by name, using a layered lookup strategy:
      1. Known aliases (instant)
      2. Known web apps (open in browser)
      3. Windows registry App Paths (fast)
      4. Common installation directories (slower, broader search)
      5. Direct `start` command fallback (let Windows resolve it)
    """
    if not app_name:
        return False

    app_lower = app_name.lower().strip().strip('"\'.')
    app_lower = re.sub(r'^(?:the|a|an)\s+', '', app_lower)
    app_lower = re.sub(r'\s+(?:app|application|program)$', '', app_lower)

    # 1. Known aliases
    if app_lower in _KNOWN_APPS:
        target = _KNOWN_APPS[app_lower]
        try:
            if target.startswith("ms-") or target.startswith("http") or target.startswith("outlook") or target.startswith("bing") or target.startswith("microsoft."):
                os.startfile(target)
            else:
                subprocess.Popen(["start", "", target], shell=True)
            logger.info(f"Opened '{app_name}' via known alias: {target}")
            return True
        except Exception as e:
            logger.warning(f"Known alias failed for '{app_name}': {e}")

    # 2. Web apps — open in default browser
    for key, url in _WEB_APPS.items():
        if key in app_lower:
            try:
                import webbrowser
                webbrowser.open(url)
                logger.info(f"Opened web app '{app_name}' at URL: {url}")
                return True
            except Exception as e:
                logger.warning(f"Failed to open web app '{app_name}': {e}")

    # 3. Windows registry lookup
    reg_path = _find_app_in_registry(app_lower)
    if reg_path:
        try:
            subprocess.Popen([reg_path])
            logger.info(f"Opened '{app_name}' via registry: {reg_path}")
            return True
        except Exception as e:
            logger.warning(f"Registry launch failed for '{app_name}': {e}")

    # 4. Common directories search
    dir_path = _find_app_in_common_dirs(app_lower)
    if dir_path:
        try:
            subprocess.Popen([dir_path])
            logger.info(f"Opened '{app_name}' via directory search: {dir_path}")
            return True
        except Exception as e:
            logger.warning(f"Directory launch failed for '{app_name}': {e}")

    # 5. Final fallback — let Windows `start` command try to resolve it
    try:
        result = subprocess.run(
            f'start "" "{app_lower}.exe"',
            shell=True,
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info(f"Opened '{app_name}' via Windows start fallback.")
            return True
    except Exception as e:
        logger.debug(f"Windows start fallback failed for '{app_name}': {e}")

    logger.warning(f"Could not find or open application: '{app_name}'")
    return False


def close_application(app_name: str) -> str:
    """
    Terminates running process(es) matching app_name using psutil.
    Returns spoken confirmation, 'doesn't seem to be running', or error message.
    """
    if not app_name:
        return "I didn't catch which application to close."

    app_clean = app_name.lower().strip().strip('"\'.')
    app_clean = re.sub(r'^(?:the|a|an)\s+', '', app_clean)
    app_clean = re.sub(r'\s+(?:app|application|program)$', '', app_clean)

    display_name = app_name.strip().title()

    # Build target matching names/stems
    targets = set()
    targets.add(app_clean)
    targets.add(f"{app_clean}.exe")

    if app_clean in _KNOWN_APPS:
        target_known = _KNOWN_APPS[app_clean].lower()
        targets.add(target_known)
        if target_known.endswith(".exe"):
            targets.add(target_known[:-4])

    for key, val in _KNOWN_APPS.items():
        if app_clean == key or key.startswith(app_clean):
            targets.add(val.lower())
            if val.lower().endswith(".exe"):
                targets.add(val.lower()[:-4])

    closed_count = 0
    permission_error = False

    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info.get('name')
                if not pname:
                    continue
                pname_lower = pname.lower()
                pname_stem = pname_lower[:-4] if pname_lower.endswith(".exe") else pname_lower

                is_match = False
                for t in targets:
                    if t and (pname_lower == t or pname_stem == t or (len(t) >= 3 and t in pname_lower)):
                        is_match = True
                        break

                if is_match:
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except psutil.AccessDenied:
                permission_error = True
                logger.warning(f"Access denied trying to terminate PID {proc.pid} ({proc.info.get('name')})")
            except Exception as e:
                logger.warning(f"Error terminating PID {proc.pid}: {e}")

        if closed_count > 0:
            logger.info(f"Closed {closed_count} process(es) matching '{app_name}'.")
            return f"Closed {display_name}"
        elif permission_error:
            return "I couldn't close that"
        else:
            return f"{display_name} doesn't seem to be running"

    except Exception as e:
        logger.exception(f"Error closing app '{app_name}': {e}")
        return "I couldn't close that"

