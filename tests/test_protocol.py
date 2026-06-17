"""Tests for the 0x55 frame parser and device-state parsing logic."""

import pytest

from nothing_app.protocol import (
    ANCMode,
    NothingDevice,
    _CMD_BATTERY,
    _CMD_EARPHONE,
    _CMD_EQ_MODE,
    _CMD_NOISE_RED,
    _CMD_REMOTE_CONF,
    _CMD_HOST_VERSION,
    _prioritise,
)
from tests.conftest import build_device_frame


# ── helpers ───────────────────────────────────────────────────────────────────


def make_device() -> NothingDevice:
    return NothingDevice("AA:BB:CC:DD:EE:FF")


# ── _prioritise ───────────────────────────────────────────────────────────────


def test_prioritise_puts_15_17_16_first():
    result = _prioritise([1, 2, 15, 16, 17, 18])
    assert result[:3] == [15, 17, 16]


def test_prioritise_only_present_channels_promoted():
    result = _prioritise([1, 2, 17])
    assert result[0] == 17
    assert set(result) == {1, 2, 17}


def test_prioritise_preserves_all_channels():
    channels = [3, 5, 15, 16, 17, 20]
    result = _prioritise(channels)
    assert sorted(result) == sorted(channels)


def test_prioritise_no_priority_channels():
    result = _prioritise([1, 2, 3])
    assert set(result) == {1, 2, 3}


# ── _parse_battery ────────────────────────────────────────────────────────────


def test_parse_battery_basic():
    dev = make_device()
    # count=3, [type=2 left=80%], [type=3 right=72%], [type=4 case=90%]
    payload = bytes([0x03, 0x02, 80, 0x03, 72, 0x04, 90])
    changed = dev._parse_battery(payload)
    assert changed is True
    assert dev.state.left_battery == 80
    assert dev.state.right_battery == 72
    assert dev.state.case_battery == 90


def test_parse_battery_charging_flag_stripped():
    dev = make_device()
    # bit7 = charging; actual percent is bits[6:0]
    payload = bytes([0x01, 0x02, 0x80 | 45])  # left=45%, charging
    dev._parse_battery(payload)
    assert dev.state.left_battery == 45


def test_parse_battery_too_short_returns_false():
    dev = make_device()
    assert dev._parse_battery(b"") is False
    assert dev._parse_battery(b"\x01\x02") is False


def test_parse_battery_no_change_returns_false():
    dev = make_device()
    payload = bytes([0x01, 0x02, 50])
    dev._parse_battery(payload)
    changed = dev._parse_battery(payload)  # same value second time
    assert changed is False


def test_parse_battery_updates_only_present_types():
    dev = make_device()
    # Only right bud present
    payload = bytes([0x01, 0x03, 60])
    dev._parse_battery(payload)
    assert dev.state.right_battery == 60
    assert dev.state.left_battery == -1  # untouched default
    assert dev.state.case_battery == -1


# ── _parse_anc ────────────────────────────────────────────────────────────────


def test_parse_anc_off():
    dev = make_device()
    # type=1 mode=OFF(5), type=2 level=2 (has ANC)
    payload = bytes([0x01, 5, 0x00, 0x02, 2, 0x00])
    dev._parse_anc(payload)
    assert dev.state.anc_mode == ANCMode.OFF


def test_parse_anc_noise_cancellation():
    dev = make_device()
    payload = bytes([0x01, 1, 0x00, 0x02, 2, 0x00])  # mode=STRONG(1)
    dev._parse_anc(payload)
    assert dev.state.anc_mode == ANCMode.NOISE_CANCELLATION


def test_parse_anc_transparency():
    dev = make_device()
    payload = bytes([0x01, 7, 0x00, 0x02, 0xFE, 0x00])  # mode=transparency, level=0xFE
    dev._parse_anc(payload)
    assert dev.state.anc_mode == ANCMode.TRANSPARENCY


def test_parse_anc_detects_full_modes_when_level_1_to_4():
    dev = make_device()
    payload = bytes([0x01, 1, 0x00, 0x02, 3, 0x00])  # level=3 → all 3 modes supported
    dev._parse_anc(payload)
    assert dev.state.supported_anc_modes == frozenset(
        [ANCMode.OFF, ANCMode.NOISE_CANCELLATION, ANCMode.TRANSPARENCY]
    )


def test_parse_anc_detects_limited_modes_when_level_0xfe():
    dev = make_device()
    payload = bytes([0x01, 7, 0x00, 0x02, 0xFE, 0x00])  # level=0xFE → off+transparency only
    dev._parse_anc(payload)
    assert dev.state.supported_anc_modes == frozenset([ANCMode.OFF, ANCMode.TRANSPARENCY])


def test_parse_anc_supported_modes_locked_after_first_level():
    dev = make_device()
    payload1 = bytes([0x01, 1, 0x00, 0x02, 2, 0x00])
    payload2 = bytes([0x01, 7, 0x00, 0x02, 0xFE, 0x00])
    dev._parse_anc(payload1)
    first = dev.state.supported_anc_modes
    dev._parse_anc(payload2)
    assert dev.state.supported_anc_modes == first  # locked after first observation


def test_parse_anc_too_short_returns_false():
    dev = make_device()
    assert dev._parse_anc(b"") is False
    assert dev._parse_anc(b"\x01\x01") is False


# ── _parse_earphone_status ────────────────────────────────────────────────────


def test_parse_earphone_both_in_ear():
    dev = make_device()
    # count=2, [type=2 left val=0x04(in_ear)], [type=3 right val=0x04]
    payload = bytes([0x02, 0x02, 0x04, 0x03, 0x04])
    changed = dev._parse_earphone_status(payload)
    assert changed is True
    assert dev.state.left_wearing is True
    assert dev.state.right_wearing is True


def test_parse_earphone_neither_in_ear():
    dev = make_device()
    dev.state.left_wearing = True
    dev.state.right_wearing = True
    payload = bytes([0x02, 0x02, 0x00, 0x03, 0x00])  # bit2 not set → not in ear
    changed = dev._parse_earphone_status(payload)
    assert changed is True
    assert dev.state.left_wearing is False
    assert dev.state.right_wearing is False


def test_parse_earphone_no_change_returns_false():
    dev = make_device()
    payload = bytes([0x02, 0x02, 0x00, 0x03, 0x00])
    dev._parse_earphone_status(payload)
    changed = dev._parse_earphone_status(payload)
    assert changed is False


def test_parse_earphone_too_short_returns_false():
    dev = make_device()
    assert dev._parse_earphone_status(b"") is False
    assert dev._parse_earphone_status(b"\x01\x02") is False


def test_parse_earphone_ignores_non_bud_types():
    dev = make_device()
    # type=4 (case), type=5 (tws) — should be ignored
    payload = bytes([0x02, 0x04, 0x04, 0x05, 0x04])
    changed = dev._parse_earphone_status(payload)
    assert changed is False


# ── _parse_remote_conf (serial number) ───────────────────────────────────────


def test_dispatch_remote_conf_parses_serial(mock_profiles):
    dev = make_device()
    # "device_id,4,SH10212543006451\n"
    raw = "1,4,SH10212543006451\n".encode()
    dev._dispatch_x55(_CMD_REMOTE_CONF, raw)
    assert dev.state.serial_number == "SH10212543006451"


def test_dispatch_remote_conf_ignores_other_fields(mock_profiles):
    dev = make_device()
    raw = "1,1,some_value\n1,2,other\n1,4,SERIAL123\n".encode()
    dev._dispatch_x55(_CMD_REMOTE_CONF, raw)
    assert dev.state.serial_number == "SERIAL123"


# ── _parse_host_version (firmware) ───────────────────────────────────────────


def test_dispatch_host_version(mock_profiles):
    dev = make_device()
    dev._dispatch_x55(_CMD_HOST_VERSION, b"2.0.5\x00")
    assert dev.state.firmware_version == "2.0.5"


# ── _process_x55 (frame parser integration) ──────────────────────────────────


def test_process_x55_battery_frame(mock_profiles):
    dev = make_device()
    payload = bytes([0x03, 0x02, 80, 0x03, 72, 0x04, 90])
    frame = build_device_frame(_CMD_BATTERY, payload)
    dev._process_x55(frame)
    assert dev.state.left_battery == 80
    assert dev.state.right_battery == 72
    assert dev.state.case_battery == 90


def test_process_x55_anc_frame(mock_profiles):
    dev = make_device()
    payload = bytes([0x01, 7, 0x00, 0x02, 0xFE, 0x00])
    frame = build_device_frame(_CMD_NOISE_RED, payload)
    dev._process_x55(frame)
    assert dev.state.anc_mode == ANCMode.TRANSPARENCY


def test_process_x55_crc_error_still_advances_buffer(mock_profiles):
    dev = make_device()
    payload = bytes([0x01, 0x02, 50])
    frame = bytearray(build_device_frame(_CMD_BATTERY, payload))
    frame[-1] ^= 0xFF  # corrupt CRC
    # Should not raise; buffer should be consumed past the bad frame
    remaining = dev._process_x55(bytes(frame))
    assert remaining == b""


def test_process_x55_incomplete_frame_held_in_buffer(mock_profiles):
    dev = make_device()
    payload = bytes([0x01, 0x02, 50])
    frame = build_device_frame(_CMD_BATTERY, payload)
    partial = frame[:5]  # only first 5 bytes
    remaining = dev._process_x55(partial)
    assert remaining == partial  # held until rest arrives


def test_process_x55_two_consecutive_frames(mock_profiles):
    dev = make_device()
    f1 = build_device_frame(_CMD_BATTERY, bytes([0x01, 0x02, 70]))
    f2 = build_device_frame(_CMD_NOISE_RED, bytes([0x01, 7, 0x00, 0x02, 0xFE, 0x00]))
    dev._process_x55(f1 + f2)
    assert dev.state.left_battery == 70
    assert dev.state.anc_mode == ANCMode.TRANSPARENCY
