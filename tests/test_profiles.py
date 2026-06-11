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
