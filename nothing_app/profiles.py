import json
import os

_DIR = os.path.expanduser("~/.config/something-x")
_PROFILES_FILE = os.path.join(_DIR, "profiles.json")
_LAST_DEV_FILE = os.path.join(_DIR, "last_device")

_NOTIFY_DEFAULTS: dict = {"battery_low": True, "connect": True, "disconnect": True}
_ALLOWED_IMPORT_KEYS = frozenset({"anc", "eq", "nickname", "notify"})


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_all() -> dict:
    try:
        with open(_PROFILES_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_all(data: dict):
    os.makedirs(_DIR, exist_ok=True)
    with open(_PROFILES_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── ANC / EQ profile ─────────────────────────────────────────────────────────


def load(address: str) -> dict:
    return _load_all().get(address, {})


def save(address: str, anc_mode: int, eq_preset: str):
    data = _load_all()
    entry = data.setdefault(address, {})
    entry["anc"] = anc_mode
    entry["eq"] = eq_preset
    _save_all(data)


# ── Device nickname ───────────────────────────────────────────────────────────


def get_nickname(address: str) -> str | None:
    return _load_all().get(address, {}).get("nickname")


def set_nickname(address: str, name: str | None):
    data = _load_all()
    entry = data.setdefault(address, {})
    if name:
        entry["nickname"] = name
    else:
        entry.pop("nickname", None)
    _save_all(data)


# ── Notification preferences ──────────────────────────────────────────────────


def get_notify_prefs(address: str) -> dict:
    """Return notification prefs for address, filling missing keys with defaults."""
    stored = _load_all().get(address, {}).get("notify", {})
    return {**_NOTIFY_DEFAULTS, **stored}


def set_notify_prefs(address: str, prefs: dict):
    data = _load_all()
    entry = data.setdefault(address, {})
    entry["notify"] = {**_NOTIFY_DEFAULTS, **entry.get("notify", {}), **prefs}
    _save_all(data)


# ── Import / export ───────────────────────────────────────────────────────────


def export_profile(address: str) -> dict:
    """Return the stored profile dict for a single device (empty dict if none)."""
    return _load_all().get(address, {})


def import_profile(address: str, data: dict):
    """Merge known keys from data into the stored profile for address."""
    all_data = _load_all()
    entry = all_data.setdefault(address, {})
    for key in _ALLOWED_IMPORT_KEYS:
        if key in data:
            entry[key] = data[key]
    _save_all(all_data)


def export_all() -> dict:
    """Return the entire profiles store as a plain dict."""
    return _load_all()


def import_all(data: dict):
    """Merge known keys from every address entry in data into the profiles store."""
    if not isinstance(data, dict):
        raise ValueError("Profile data must be a JSON object")
    all_data = _load_all()
    for address, entry in data.items():
        if not isinstance(entry, dict):
            continue
        existing = all_data.setdefault(address, {})
        for key in _ALLOWED_IMPORT_KEYS:
            if key in entry:
                existing[key] = entry[key]
    _save_all(all_data)


# ── Last device ───────────────────────────────────────────────────────────────


def get_last_device() -> str | None:
    try:
        with open(_LAST_DEV_FILE) as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def set_last_device(address: str):
    os.makedirs(_DIR, exist_ok=True)
    with open(_LAST_DEV_FILE, "w") as f:
        f.write(address)
