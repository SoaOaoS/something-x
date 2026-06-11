"""Tests for notification gating — battery low, connect, disconnect."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from nothing_app import profiles
from nothing_app.protocol import NothingDevice


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "_DIR", str(tmp_path))
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    monkeypatch.setattr(profiles, "_LAST_DEV_FILE", str(tmp_path / "last_device"))


_ADDR = "AA:BB:CC:DD:EE:FF"


def _make_device() -> NothingDevice:
    return NothingDevice(_ADDR)


def _fire_low_battery(dev: NothingDevice, pct: int = 10):
    """Simulate a low-battery reading that is NOT the first observation."""
    dev._low_bat_seen.add("left")
    dev._check_low_battery("left", pct, "Left earbud")


# ── battery_low pref ──────────────────────────────────────────────────────────


def test_battery_low_notification_sent_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    profiles.set_notify_prefs(_ADDR, {"battery_low": True})

    fired = threading.Event()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        fired.set()

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _fire_low_battery(dev)
        fired.wait(timeout=2)

    assert any("notify-send" in c for c in calls), "notify-send should have been called"


def test_battery_low_notification_suppressed_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    profiles.set_notify_prefs(_ADDR, {"battery_low": False})

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _fire_low_battery(dev)
        # Give the thread a moment in case it was incorrectly spawned
        import time

        time.sleep(0.1)

    assert not calls, "notify-send should NOT have been called"


def test_battery_low_not_sent_on_first_reading():
    """First battery reading after connect should never trigger a notification."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        # Do NOT pre-seed _low_bat_seen — this is the first reading
        dev._check_low_battery("left", 5, "Left earbud")
        import time

        time.sleep(0.1)

    assert not calls


def test_battery_low_deduplicates_threshold():
    """Each threshold fires at most once per connection even with repeated low readings."""
    fired_count = [0]
    lock = threading.Lock()

    def fake_run(cmd, **kwargs):
        with lock:
            fired_count[0] += 1

    dev = _make_device()
    dev._low_bat_seen.add("left")
    # Pre-mark all thresholds as already notified so repeat calls cannot fire.
    dev._low_bat_notified["left"] = set(dev._LOW_BAT_THRESHOLDS)

    with patch("nothing_app.protocol.subprocess.run", fake_run):
        dev._check_low_battery("left", 5, "Left earbud")
        dev._check_low_battery("left", 5, "Left earbud")
        import time

        time.sleep(0.1)

    assert fired_count[0] == 0, "all thresholds already notified — should not fire again"


# ── notify_prefs defaults ─────────────────────────────────────────────────────


def test_battery_low_sent_with_default_prefs():
    """With no stored prefs, battery_low defaults to True → notification fires."""
    fired = threading.Event()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        fired.set()

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _fire_low_battery(dev)
        fired.wait(timeout=2)

    assert calls
