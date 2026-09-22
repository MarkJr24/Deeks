import os
import shutil
import send2trash
from logger import logger

USER_HOME = os.path.expanduser("~")

# Configurable search directories for Deeks file operations
COMMON_SEARCH_FOLDERS = [
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Documents"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(USER_HOME, "Pictures")
]


def _find_matching_items(target_name: str) -> list[dict]:
    """
    Searches COMMON_SEARCH_FOLDERS for files or directories matching target_name.
    Prioritizes exact case-insensitive matches, followed by substring matches.
    """
    clean_target = target_name.strip().lower()
    if not clean_target:
        return []

    exact_matches = []
    partial_matches = []

    for folder in COMMON_SEARCH_FOLDERS:
        if not os.path.exists(folder):
            continue
        try:
            for item in os.listdir(folder):
                item_lower = item.lower()
                full_path = os.path.join(folder, item)
                item_info = {
                    "name": item,
                    "path": full_path,
                    "is_dir": os.path.isdir(full_path),
                    "parent": os.path.basename(folder)
                }

                if item_lower == clean_target:
                    exact_matches.append(item_info)
                elif clean_target in item_lower:
                    partial_matches.append(item_info)
        except Exception as e:
            logger.warning(f"Error scanning directory '{folder}' for file management: {e}")

    return exact_matches if exact_matches else partial_matches


def open_file_or_folder(name: str, speak_func=None, listen_func=None) -> str:
    """
    Searches common user folders for a matching file/folder and opens it.
    If multiple matches are found, prompts the user to specify which one.
    """
    logger.info(f"[File Management] Opening file or folder matching: '{name}'")
    matches = _find_matching_items(name)

    if not matches:
        msg = f"I couldn't find any file or folder named '{name}' in Desktop, Documents, Downloads, or Pictures."
        logger.info(f"[File Management] {msg}")
        return msg

    if len(matches) == 1:
        target = matches[0]
        try:
            os.startfile(target["path"])
            msg = f"Opening {target['name']} from {target['parent']}."
            logger.info(f"[File Management] {msg}")
            return msg
        except Exception as e:
            logger.exception(f"Error opening '{target['path']}': {e}")
            return f"I found {target['name']} but encountered an error opening it."

    # Multiple matches found
    option_names = [f"{m['name']} in {m['parent']}" for m in matches[:4]]
    options_str = ", ".join(option_names)

    if speak_func and listen_func:
        prompt = f"I found multiple items matching '{name}': {options_str}. Which one would you like to open?"
        logger.info(f"[File Management] Multiple matches found. Prompting: '{prompt}'")
        speak_func(prompt)
        response = listen_func()
        logger.info(f"[File Management] User response: '{response}'")

        if response:
            resp_lower = response.lower()
            for m in matches:
                if m['name'].lower() in resp_lower or m['parent'].lower() in resp_lower:
                    try:
                        os.startfile(m["path"])
                        return f"Opening {m['name']}."
                    except Exception as e:
                        logger.exception(f"Error opening '{m['path']}': {e}")
                        return f"Error opening {m['name']}."

        return f"Multiple matches were found ({options_str}), but I didn't catch which one you wanted."
    else:
        return f"I found multiple matches: {options_str}. Please specify which one you'd like to open."


def create_folder(folder_name: str, parent_dir: str = None) -> str:
    """
    Creates a new directory with folder_name.
    Defaults to creating on the Desktop unless parent_dir is specified.
    """
    clean_name = folder_name.strip()
    if not clean_name:
        return "Please specify a name for the new folder."

    target_dir = parent_dir if parent_dir else os.path.join(USER_HOME, "Desktop")
    new_path = os.path.join(target_dir, clean_name)

    logger.info(f"[File Management] Creating folder: '{new_path}'")
    try:
        if os.path.exists(new_path):
            return f"A folder named '{clean_name}' already exists on your Desktop."
        os.makedirs(new_path, exist_ok=True)
        return f"Created folder '{clean_name}' on your Desktop."
    except Exception as e:
        logger.exception(f"Error creating folder '{new_path}': {e}")
        return f"Failed to create folder '{clean_name}'."


def delete_file_or_folder(target_name: str, speak_func=None, listen_func=None) -> str:
    """
    Finds matching item and moves it to the Windows Recycle Bin (send2trash) after voice confirmation.
    """
    logger.info(f"[File Management] Delete request for: '{target_name}'")
    matches = _find_matching_items(target_name)

    if not matches:
        return f"I couldn't find any file or folder named '{target_name}' to delete."

    target = matches[0]

    # Spoken confirmation step for destructive action
    if speak_func and listen_func:
        prompt = f"Are you sure you want to delete {target['name']} from {target['parent']}? Say yes to confirm."
        logger.info(f"[File Management] Asking deletion confirmation: '{prompt}'")
        speak_func(prompt)
        response = listen_func()
        logger.info(f"[File Management] User confirmation response: '{response}'")

        if response and any(kw in response.lower() for kw in ["yes", "confirm", "yeah", "yep", "sure", "do it"]):
            try:
                send2trash.send2trash(target["path"])
                logger.info(f"[File Management] Successfully moved '{target['path']}' to Recycle Bin.")
                return f"Moved {target['name']} to the Recycle Bin."
            except Exception as e:
                logger.exception(f"Error sending '{target['path']}' to Recycle Bin: {e}")
                return f"Failed to delete {target['name']}."
        else:
            logger.info(f"[File Management] Deletion of '{target['name']}' cancelled by user.")
            return f"Deletion of {target['name']} cancelled."
    else:
        # Without interactive confirmation, safety requires refusing auto-deletion
        return f"Deletion of '{target['name']}' requires voice confirmation."


def rename_file_or_folder(old_name: str, new_name: str, speak_func=None, listen_func=None) -> str:
    """
    Renames a matching file or folder to new_name after voice confirmation.
    """
    logger.info(f"[File Management] Rename request: '{old_name}' -> '{new_name}'")
    clean_old = old_name.strip()
    clean_new = new_name.strip()

    if not clean_old or not clean_new:
        return "Please specify both the original name and the new name."

    matches = _find_matching_items(clean_old)
    if not matches:
        return f"I couldn't find any file or folder named '{clean_old}' to rename."

    target = matches[0]
    parent_folder = os.path.dirname(target["path"])
    destination_path = os.path.join(parent_folder, clean_new)

    if speak_func and listen_func:
        prompt = f"Are you sure you want to rename {target['name']} to {clean_new}? Say yes to confirm."
        logger.info(f"[File Management] Asking rename confirmation: '{prompt}'")
        speak_func(prompt)
        response = listen_func()
        logger.info(f"[File Management] User confirmation response: '{response}'")

        if response and any(kw in response.lower() for kw in ["yes", "confirm", "yeah", "yep", "sure", "do it"]):
            try:
                os.rename(target["path"], destination_path)
                logger.info(f"[File Management] Renamed '{target['path']}' to '{destination_path}'.")
                return f"Renamed {target['name']} to {clean_new}."
            except Exception as e:
                logger.exception(f"Error renaming '{target['path']}' to '{destination_path}': {e}")
                return f"Failed to rename {target['name']}."
        else:
            return f"Renaming of {target['name']} cancelled."
    else:
        return f"Renaming '{target['name']}' requires voice confirmation."
