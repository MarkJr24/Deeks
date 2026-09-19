import json
import os
import time

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "data.json")

# ── Short-lived read cache so repeated load_memory() calls don't hammer disk ─
_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL: float = 3.0   # seconds — writes always invalidate immediately

def _load_all() -> dict:
    global _cache, _cache_ts
    now = time.time()
    if now - _cache_ts < _CACHE_TTL:
        return dict(_cache)          # return a copy so callers can't mutate
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        _cache_ts = now
        return dict(_cache)
    except Exception:
        return {}

def _save_all(data: dict) -> None:
    global _cache, _cache_ts
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    # Invalidate cache immediately so the next read picks up the new value
    _cache = dict(data)
    _cache_ts = time.time()

def save_memory(key, value) -> None:
    data = _load_all()
    data[key] = value
    _save_all(data)

def load_memory(key):
    return _load_all().get(key)

def add_user_fact(fact: str):
    """Adds a permanent fact about the user to the memory store."""
    data = _load_all()
    if "user_facts" not in data:
        data["user_facts"] = []
    if fact not in data["user_facts"]:
        data["user_facts"].append(fact)
        _save_all(data)

def get_user_facts() -> list:
    """Returns a list of all known facts about the user."""
    data = _load_all()
    return data.get("user_facts", [])
