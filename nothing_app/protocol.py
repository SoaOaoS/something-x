import socket
import struct
import threading
from dataclasses import dataclass
from gi.repository import GLib, GObject

RFCOMM_CHANNEL = 5
PACKET_MAGIC = b"\xab\xcd"
RESPONSE_MAGIC = b"\xef\xcd"

CMD_GET_BATTERY = 0x0001
CMD_GET_ANC_MODE = 0x0003
CMD_SET_ANC_MODE = 0x0002
CMD_GET_EQ = 0x0005
CMD_SET_EQ = 0x0004
CMD_GET_IN_EAR = 0x0011
CMD_SET_IN_EAR = 0x0010
CMD_GET_DEVICE_INFO = 0x000a
CMD_GET_WEAR_STATE = 0x0020


class ANCMode:
    OFF = 0
    NOISE_CANCELLATION = 1
    TRANSPARENCY = 2
    LABELS = {OFF: "Off", NOISE_CANCELLATION: "ANC", TRANSPARENCY: "Transparency"}


EQ_PRESETS = {
    "Balanced": 0,
    "More Bass": 1,
    "More Treble": 2,
    "Voice": 3,
}
EQ_PRESET_NAMES = {v: k for k, v in EQ_PRESETS.items()}


@dataclass
class DeviceState:
    left_battery: int = -1
    right_battery: int = -1
    case_battery: int = -1
    anc_mode: int = ANCMode.OFF
    eq_preset: str = "Balanced"
    in_ear_detection: bool = True
    auto_pause: bool = True
    firmware_version: str = "—"
    serial_number: str = "—"
    left_wearing: bool = False
    right_wearing: bool = False


class NothingDevice(GObject.Object):
    __gsignals__ = {
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "connected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "disconnected": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, address: str):
        super().__init__()
        self.address = address
        self.state = DeviceState()
        self._sock: socket.socket | None = None
        self._rfcomm_connected = False
        self._thread: threading.Thread | None = None

    def connect_rfcomm(self, channel: int = RFCOMM_CHANNEL):
        def _run():
            for ch in [channel, 3, 8, 1]:
                try:
                    sock = socket.socket(
                        socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
                    )
                    sock.settimeout(6)
                    sock.connect((self.address, ch))
                    self._sock = sock
                    self._rfcomm_connected = True
                    GLib.idle_add(self.emit, "connected")
                    self._request_initial_state()
                    self._recv_loop()
                    return
                except OSError:
                    continue
            print(f"[protocol] Could not open RFCOMM to {self.address}")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def disconnect_rfcomm(self):
        self._rfcomm_connected = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @property
    def rfcomm_connected(self) -> bool:
        return self._rfcomm_connected

    def set_anc_mode(self, mode: int):
        self.state.anc_mode = mode
        self._send(CMD_SET_ANC_MODE, bytes([mode]))
        GLib.idle_add(self.emit, "state-changed")

    def set_eq_preset(self, preset: str):
        self.state.eq_preset = preset
        preset_id = EQ_PRESETS.get(preset, 0)
        self._send(CMD_SET_EQ, bytes([preset_id]))
        GLib.idle_add(self.emit, "state-changed")

    def set_in_ear_detection(self, enabled: bool):
        self.state.in_ear_detection = enabled
        self._send(CMD_SET_IN_EAR, bytes([int(enabled)]))
        GLib.idle_add(self.emit, "state-changed")

    def _request_initial_state(self):
        for cmd in (CMD_GET_BATTERY, CMD_GET_ANC_MODE, CMD_GET_EQ,
                    CMD_GET_IN_EAR, CMD_GET_DEVICE_INFO):
            self._send(cmd)

    def _send(self, cmd_id: int, payload: bytes = b""):
        if not self._rfcomm_connected or not self._sock:
            return
        packet = PACKET_MAGIC + struct.pack(">HH", cmd_id, len(payload)) + payload
        try:
            self._sock.sendall(packet)
        except OSError as exc:
            print(f"[protocol] send error: {exc}")
            self._handle_disconnect()

    def _recv_loop(self):
        buf = b""
        while self._rfcomm_connected and self._sock:
            try:
                chunk = self._sock.recv(128)
                if not chunk:
                    break
                buf += chunk
                buf = self._process_buf(buf)
            except socket.timeout:
                continue
            except OSError:
                break
        self._handle_disconnect()

    def _process_buf(self, buf: bytes) -> bytes:
        while len(buf) >= 6:
            if buf[:2] not in (PACKET_MAGIC, RESPONSE_MAGIC):
                buf = buf[1:]
                continue
            cmd_id = struct.unpack(">H", buf[2:4])[0]
            length = struct.unpack(">H", buf[4:6])[0]
            if len(buf) < 6 + length:
                break
            payload = buf[6 : 6 + length]
            self._dispatch(cmd_id, payload)
            buf = buf[6 + length :]
        return buf

    def _dispatch(self, cmd_id: int, payload: bytes):
        changed = False
        if cmd_id == CMD_GET_BATTERY and len(payload) >= 3:
            self.state.left_battery = int(payload[0])
            self.state.right_battery = int(payload[1])
            self.state.case_battery = int(payload[2])
            changed = True
        elif cmd_id == CMD_GET_ANC_MODE and payload:
            self.state.anc_mode = int(payload[0])
            changed = True
        elif cmd_id == CMD_GET_EQ and payload:
            self.state.eq_preset = EQ_PRESET_NAMES.get(int(payload[0]), "Balanced")
            changed = True
        elif cmd_id == CMD_GET_IN_EAR and payload:
            self.state.in_ear_detection = bool(payload[0])
            changed = True
        elif cmd_id == CMD_GET_DEVICE_INFO and len(payload) >= 2:
            try:
                fw_len = payload[0]
                self.state.firmware_version = payload[1 : 1 + fw_len].decode(errors="replace")
                remaining = payload[1 + fw_len :]
                if remaining:
                    sn_len = remaining[0]
                    self.state.serial_number = remaining[1 : 1 + sn_len].decode(errors="replace")
            except Exception:
                pass
            changed = True
        elif cmd_id == CMD_GET_WEAR_STATE and len(payload) >= 2:
            self.state.left_wearing = bool(payload[0])
            self.state.right_wearing = bool(payload[1])
            changed = True

        if changed:
            GLib.idle_add(self.emit, "state-changed")

    def _handle_disconnect(self):
        self._rfcomm_connected = False
        self._sock = None
        GLib.idle_add(self.emit, "disconnected")
