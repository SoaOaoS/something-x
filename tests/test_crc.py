import struct

from nothing_app.protocol import _CMD_PROTO_VERSION, _CTRL_HOST_CRC, _SOF, _crc16


def test_returns_uint16():
    for data in [b"", b"\x00", b"\xff", b"\x55" * 8, b"hello world"]:
        result = _crc16(data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF


def test_deterministic():
    data = b"\x55\x60\x01\x01\xc0\x00\x00\x01"
    assert _crc16(data) == _crc16(data)


def test_empty_is_init_value():
    # With no bytes processed the accumulator stays at the init value 0xFFFF.
    assert _crc16(b"") == 0xFFFF


def test_single_bit_flip_detected():
    data = b"\x55\x60\x01\x01\xc0\x00\x00\x01\x42\xab"
    flipped = bytes([data[0] ^ 0x01]) + data[1:]
    assert _crc16(data) != _crc16(flipped)


def test_different_inputs_differ():
    assert _crc16(b"\x00\x00") != _crc16(b"\x00\x01")
    assert _crc16(b"\x55\x60\x01") != _crc16(b"\x55\x60\x02")
    assert _crc16(b"\xaa") != _crc16(b"\xab")


def test_probe_frame_crc_is_stable():
    # The probe frame sent during channel discovery must always produce the same CRC.
    header = struct.pack("<BHHH", _SOF, _CTRL_HOST_CRC, _CMD_PROTO_VERSION, 0) + bytes([0x01])
    crc1 = _crc16(header)
    crc2 = _crc16(header)
    assert crc1 == crc2
    assert 0 <= crc1 <= 0xFFFF


def test_payload_changes_crc():
    header = struct.pack("<BHHH", _SOF, _CTRL_HOST_CRC, _CMD_PROTO_VERSION, 3) + bytes([0x01])
    crc_a = _crc16(header + b"\x01\x02\x03")
    crc_b = _crc16(header + b"\x01\x02\x04")
    assert crc_a != crc_b
