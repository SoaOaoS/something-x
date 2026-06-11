import struct
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_glib(monkeypatch):
    """Replace GLib scheduling calls with no-ops so tests don't need a running main loop."""
    from gi.repository import GLib

    monkeypatch.setattr(GLib, "idle_add", MagicMock(return_value=0))
    monkeypatch.setattr(GLib, "timeout_add", MagicMock(return_value=0))
    monkeypatch.setattr(GLib, "timeout_add_seconds", MagicMock(return_value=0))
    monkeypatch.setattr(GLib, "source_remove", MagicMock(return_value=True))


@pytest.fixture()
def mock_profiles(monkeypatch):
    from nothing_app import profiles

    monkeypatch.setattr(profiles, "save", MagicMock())
    monkeypatch.setattr(profiles, "load", MagicMock(return_value={}))
    monkeypatch.setattr(profiles, "set_last_device", MagicMock())


def build_device_frame(cmd_id: int, payload: bytes = b"", fsn: int = 1) -> bytes:
    """Build a 0x55 device-response frame (with CRC) for the given command and payload.

    Device responses have bit15 of cmd cleared; _process_x55 restores it via | 0x8000.
    ctrl=0x0160 has bit5 set → CRC appended.
    """
    SOF = 0x55
    CTRL = 0x0160
    cmd_raw = cmd_id & 0x7FFF  # device clears bit15 on responses
    header = struct.pack("<BHHH", SOF, CTRL, cmd_raw, len(payload)) + bytes([fsn])
    from nothing_app.protocol import _crc16

    crc = _crc16(header + payload)
    return header + payload + struct.pack("<H", crc)
