import json
import os

_DIR = os.path.expanduser("~/.config/something-x")
_PROFILES_FILE = os.path.join(_DIR, "profiles.json")
_LAST_DEV_FILE = os.path.join(_DIR, "last_device")


def load(address: str) -> dict:
    try:
        with open(_PROFILES_FILE) as f:
            return json.load(f).get(address, {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(address: str, anc_mode: int, eq_preset: str):
    os.makedirs(_DIR, exist_ok=True)
    data = {}
    try:
        with open(_PROFILES_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data[address] = {"anc": anc_mode, "eq": eq_preset}
    with open(_PROFILES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_last_device() -> str | None:
    try:
        addr = open(_LAST_DEV_FILE).read().strip()
        return addr or None
    except FileNotFoundError:
        return None


def set_last_device(address: str):
    os.makedirs(_DIR, exist_ok=True)
    with open(_LAST_DEV_FILE, "w") as f:
        f.write(address)
