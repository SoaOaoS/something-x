"""Tests for the profiles persistence layer."""

import json
import os

import pytest

from nothing_app import profiles
from nothing_app.protocol import ANCMode


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the profiles module at a temp directory so tests never touch ~/.config."""
    monkeypatch.setattr(profiles, "_DIR", str(tmp_path))
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    monkeypatch.setattr(profiles, "_LAST_DEV_FILE", str(tmp_path / "last_device"))


# ── load ──────────────────────────────────────────────────────────────────────


def test_load_missing_file_returns_empty():
    result = profiles.load("AA:BB:CC:DD:EE:FF")
    assert result == {}


def test_load_bad_json_returns_empty(tmp_path):
    (tmp_path / "profiles.json").write_text("not json")
    result = profiles.load("AA:BB:CC:DD:EE:FF")
    assert result == {}


def test_load_unknown_address_returns_empty():
    profiles.save("11:22:33:44:55:66", ANCMode.OFF, "Balanced")
    result = profiles.load("AA:BB:CC:DD:EE:FF")
    assert result == {}


# ── save / load roundtrip ─────────────────────────────────────────────────────


def test_save_and_load_roundtrip():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.save(addr, ANCMode.NOISE_CANCELLATION, "More Bass")
    p = profiles.load(addr)
    assert p["anc"] == ANCMode.NOISE_CANCELLATION
    assert p["eq"] == "More Bass"


def test_save_multiple_devices():
    profiles.save("AA:BB:CC:DD:EE:FF", ANCMode.OFF, "Balanced")
    profiles.save("11:22:33:44:55:66", ANCMode.TRANSPARENCY, "Voice")
    assert profiles.load("AA:BB:CC:DD:EE:FF")["anc"] == ANCMode.OFF
    assert profiles.load("11:22:33:44:55:66")["anc"] == ANCMode.TRANSPARENCY


def test_save_overwrites_existing():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.save(addr, ANCMode.OFF, "Balanced")
    profiles.save(addr, ANCMode.NOISE_CANCELLATION, "More Treble")
    p = profiles.load(addr)
    assert p["anc"] == ANCMode.NOISE_CANCELLATION
    assert p["eq"] == "More Treble"


def test_save_creates_directory(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "nested"
    monkeypatch.setattr(profiles, "_DIR", str(nested))
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(nested / "profiles.json"))
    profiles.save("AA:BB:CC:DD:EE:FF", ANCMode.OFF, "Balanced")
    assert (nested / "profiles.json").exists()


# ── last_device ───────────────────────────────────────────────────────────────


def test_get_last_device_missing_returns_none():
    assert profiles.get_last_device() is None


def test_set_and_get_last_device():
    profiles.set_last_device("AA:BB:CC:DD:EE:FF")
    assert profiles.get_last_device() == "AA:BB:CC:DD:EE:FF"


def test_set_last_device_overwrites():
    profiles.set_last_device("11:22:33:44:55:66")
    profiles.set_last_device("AA:BB:CC:DD:EE:FF")
    assert profiles.get_last_device() == "AA:BB:CC:DD:EE:FF"


# ── save preserves other fields ───────────────────────────────────────────────


def test_save_preserves_nickname():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_nickname(addr, "My Ears")
    profiles.save(addr, ANCMode.OFF, "Balanced")
    assert profiles.get_nickname(addr) == "My Ears"


def test_save_preserves_notify_prefs():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_notify_prefs(addr, {"battery_low": False})
    profiles.save(addr, ANCMode.OFF, "Balanced")
    assert profiles.get_notify_prefs(addr)["battery_low"] is False


# ── nickname ──────────────────────────────────────────────────────────────────


def test_get_nickname_none_when_not_set():
    assert profiles.get_nickname("AA:BB:CC:DD:EE:FF") is None


def test_set_and_get_nickname():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_nickname(addr, "Studio Buds")
    assert profiles.get_nickname(addr) == "Studio Buds"


def test_nickname_cleared_by_none():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_nickname(addr, "Studio Buds")
    profiles.set_nickname(addr, None)
    assert profiles.get_nickname(addr) is None


def test_nickname_cleared_by_empty_string():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_nickname(addr, "Studio Buds")
    profiles.set_nickname(addr, "")
    assert profiles.get_nickname(addr) is None


def test_nickname_does_not_affect_other_device():
    profiles.set_nickname("AA:BB:CC:DD:EE:FF", "Mine")
    assert profiles.get_nickname("11:22:33:44:55:66") is None


# ── notify_prefs ──────────────────────────────────────────────────────────────


def test_get_notify_prefs_defaults():
    prefs = profiles.get_notify_prefs("AA:BB:CC:DD:EE:FF")
    assert prefs == {"battery_low": True, "connect": True, "disconnect": True, "wear_mpris": False}


def test_set_notify_prefs_roundtrip():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_notify_prefs(addr, {"battery_low": False, "connect": False, "disconnect": False})
    prefs = profiles.get_notify_prefs(addr)
    assert prefs["battery_low"] is False
    assert prefs["connect"] is False
    assert prefs["disconnect"] is False


def test_set_notify_prefs_partial_does_not_clobber_others():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.set_notify_prefs(addr, {"battery_low": False})
    prefs = profiles.get_notify_prefs(addr)
    assert prefs["battery_low"] is False
    assert prefs["connect"] is True
    assert prefs["disconnect"] is True


def test_notify_prefs_independent_per_device():
    profiles.set_notify_prefs("AA:BB:CC:DD:EE:FF", {"battery_low": False})
    prefs_other = profiles.get_notify_prefs("11:22:33:44:55:66")
    assert prefs_other["battery_low"] is True


# ── export / import single profile ────────────────────────────────────────────


def test_export_profile_returns_stored_data():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.save(addr, ANCMode.NOISE_CANCELLATION, "More Bass")
    profiles.set_nickname(addr, "Workout")
    data = profiles.export_profile(addr)
    assert data["anc"] == ANCMode.NOISE_CANCELLATION
    assert data["eq"] == "More Bass"
    assert data["nickname"] == "Workout"


def test_export_profile_missing_returns_empty():
    assert profiles.export_profile("AA:BB:CC:DD:EE:FF") == {}


def test_import_profile_merges_known_keys():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.save(addr, ANCMode.OFF, "Balanced")
    profiles.import_profile(addr, {"eq": "More Treble", "nickname": "Imported"})
    p = profiles.load(addr)
    assert p["anc"] == ANCMode.OFF
    assert p["eq"] == "More Treble"
    assert profiles.get_nickname(addr) == "Imported"


def test_import_profile_ignores_unknown_keys():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.import_profile(addr, {"eq": "Voice", "malicious": "data"})
    raw = profiles.export_profile(addr)
    assert "malicious" not in raw


def test_import_export_roundtrip():
    addr = "AA:BB:CC:DD:EE:FF"
    profiles.save(addr, ANCMode.TRANSPARENCY, "Voice")
    profiles.set_nickname(addr, "Travel")
    profiles.set_notify_prefs(addr, {"battery_low": False})
    exported = profiles.export_profile(addr)

    # Wipe and re-import
    profiles.import_profile("BB:CC:DD:EE:FF:00", exported)
    p2 = profiles.load("BB:CC:DD:EE:FF:00")
    assert p2["anc"] == ANCMode.TRANSPARENCY
    assert p2["eq"] == "Voice"
    assert profiles.get_nickname("BB:CC:DD:EE:FF:00") == "Travel"


# ── export / import all profiles ──────────────────────────────────────────────


def test_export_all_returns_full_dict():
    profiles.save("AA:BB:CC:DD:EE:FF", ANCMode.OFF, "Balanced")
    profiles.save("11:22:33:44:55:66", ANCMode.TRANSPARENCY, "Voice")
    all_data = profiles.export_all()
    assert "AA:BB:CC:DD:EE:FF" in all_data
    assert "11:22:33:44:55:66" in all_data


def test_import_all_merges_multiple_devices():
    incoming = {
        "AA:BB:CC:DD:EE:FF": {"anc": ANCMode.NOISE_CANCELLATION, "eq": "More Bass"},
        "11:22:33:44:55:66": {"eq": "Voice", "nickname": "Partner"},
    }
    profiles.import_all(incoming)
    assert profiles.load("AA:BB:CC:DD:EE:FF")["anc"] == ANCMode.NOISE_CANCELLATION
    assert profiles.get_nickname("11:22:33:44:55:66") == "Partner"


def test_import_all_raises_on_non_dict():
    import pytest

    with pytest.raises(ValueError):
        profiles.import_all("not a dict")


def test_import_all_skips_non_dict_entries():
    profiles.import_all({"AA:BB:CC:DD:EE:FF": "bad_entry"})
    assert profiles.load("AA:BB:CC:DD:EE:FF") == {}


def test_export_all_import_all_roundtrip():
    profiles.save("AA:BB:CC:DD:EE:FF", ANCMode.OFF, "Balanced")
    profiles.set_nickname("AA:BB:CC:DD:EE:FF", "Home")
    snapshot = profiles.export_all()

    # Reset and restore
    import json as _json

    profiles._save_all({})
    profiles.import_all(snapshot)
    assert profiles.load("AA:BB:CC:DD:EE:FF")["eq"] == "Balanced"
    assert profiles.get_nickname("AA:BB:CC:DD:EE:FF") == "Home"
