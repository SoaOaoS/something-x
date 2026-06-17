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


# ── wear_mpris pref ───────────────────────────────────────────────────────────


def _set_wearing(dev: NothingDevice, left: bool, right: bool):
    """Directly update wearing state and call the MPRIS check."""
    dev.state.left_wearing = left
    dev.state.right_wearing = right
    dev._check_wear_mpris()


def test_wear_mpris_pauses_when_both_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    profiles.set_notify_prefs(_ADDR, {"wear_mpris": True})

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _set_wearing(dev, True, True)  # both wearing
        _set_wearing(dev, False, False)  # both removed → pause
        import time

        time.sleep(0.05)

    assert any("pause" in c for c in calls)


def test_wear_mpris_resumes_when_reinserted(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    profiles.set_notify_prefs(_ADDR, {"wear_mpris": True})

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _set_wearing(dev, True, True)
        _set_wearing(dev, False, False)  # pause
        _set_wearing(dev, True, False)  # one bud back in → play
        import time

        time.sleep(0.05)

    cmds = [c[-1] for c in calls]
    assert "pause" in cmds
    assert "play" in cmds


def test_wear_mpris_disabled_by_default():
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _set_wearing(dev, True, True)
        _set_wearing(dev, False, False)
        import time

        time.sleep(0.05)

    assert not calls, "wear_mpris is opt-in — should not fire with default prefs"


def test_wear_mpris_no_double_play(tmp_path, monkeypatch):
    """Wearing state bouncing while already in-ear should not trigger repeated plays."""
    monkeypatch.setattr(profiles, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    profiles.set_notify_prefs(_ADDR, {"wear_mpris": True})

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    dev = _make_device()
    with patch("nothing_app.protocol.subprocess.run", fake_run):
        _set_wearing(dev, True, True)
        _set_wearing(dev, False, False)  # pause
        _set_wearing(dev, True, False)  # play
        _set_wearing(dev, True, True)  # still wearing — no extra play
        import time

        time.sleep(0.05)

    play_calls = [c for c in calls if "play" in c]
    assert len(play_calls) == 1
