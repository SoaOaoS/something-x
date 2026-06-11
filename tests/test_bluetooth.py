"""Tests for BluetoothDevice data class and device_icon_name helper."""

import pytest

from nothing_app.bluetooth import BluetoothDevice, device_icon_name


def make_device(name="Nothing Ear (2)", icon="audio-headphones", connected=False):
    return BluetoothDevice(
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        {
            "Address": "AA:BB:CC:DD:EE:FF",
            "Name": name,
            "Icon": icon,
            "Connected": connected,
            "Paired": True,
        },
    )


# ── BluetoothDevice construction ──────────────────────────────────────────────


def test_address_stored():
    dev = make_device()
    assert dev.address == "AA:BB:CC:DD:EE:FF"


def test_name_stored():
    dev = make_device(name="CMF Buds Pro 2")
    assert dev.name == "CMF Buds Pro 2"


def test_connected_flag():
    assert make_device(connected=True).connected is True
    assert make_device(connected=False).connected is False


def test_is_nothing_true_for_known_patterns():
    for name in [
        "Nothing Ear (2)",
        "Nothing Ear (1)",
        "Nothing Ear (A)",
        "Ear (Stick)",
        "CMF Buds Pro 2",
        "CMF Earphone 1",
        "Nothing Phone (2)",
    ]:
        assert make_device(name=name).is_nothing is True, f"{name!r} should be recognised"


def test_is_nothing_false_for_unknown():
    for name in ["AirPods Pro", "Galaxy Buds2", "Sony WH-1000XM5", "Jabra Elite 7"]:
        assert make_device(name=name).is_nothing is False


def test_battery_default_none():
    assert make_device().battery is None


def test_repr_connected():
    dev = make_device(connected=True)
    assert "●" in repr(dev)


def test_repr_disconnected():
    dev = make_device(connected=False)
    assert "○" in repr(dev)


# ── BluetoothDevice.update ────────────────────────────────────────────────────


def test_update_connected():
    dev = make_device(connected=False)
    dev.update({"Connected": True})
    assert dev.connected is True


def test_update_name():
    dev = make_device(name="Old Name")
    dev.update({"Name": "New Name"})
    assert dev.name == "New Name"


def test_update_ignores_unknown_keys():
    dev = make_device()
    dev.update({"UnknownKey": "value"})  # should not raise


def test_update_alias_only_when_name_empty():
    dev = BluetoothDevice("/path", {"Address": "AA:BB:CC:DD:EE:FF", "Name": "", "Alias": "My Device"})
    dev.update({"Alias": "Better Name"})
    assert dev.name == "Better Name"

    dev2 = make_device(name="Existing")
    dev2.update({"Alias": "Should Not Replace"})
    assert dev2.name == "Existing"


# ── device_icon_name ──────────────────────────────────────────────────────────


def test_none_device_returns_default():
    assert device_icon_name(None) == "audio-headphones-symbolic"


def test_headphones_icon_mapped():
    dev = make_device(icon="audio-headphones")
    assert device_icon_name(dev) == "audio-headphones-symbolic"


def test_headset_icon_mapped():
    dev = make_device(icon="audio-headset")
    assert device_icon_name(dev) == "audio-headset-symbolic"


def test_watch_name_returns_alarm():
    for name in ["Galaxy Watch 5", "Amazfit GTR", "Fenix 7"]:
        dev = make_device(name=name)
        assert device_icon_name(dev) == "alarm-symbolic", f"expected alarm for {name!r}"


def test_ear_stick_returns_microphone():
    dev = make_device(name="Nothing Ear (Stick)")
    assert device_icon_name(dev) == "audio-input-microphone-symbolic"


def test_phone_name_returns_phone():
    dev = make_device(name="Nothing Phone (2)", icon="unknown-icon")
    assert device_icon_name(dev) == "phone-symbolic"


def test_unknown_icon_falls_back_to_headphones():
    dev = make_device(name="Random Gadget", icon="unknown-xyz")
    assert device_icon_name(dev) == "audio-headphones-symbolic"
