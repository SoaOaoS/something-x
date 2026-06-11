import os
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from gi.repository import GLib, GObject

_DEBUG = bool(os.getenv("SOMETHING_X_DEBUG"))
_QUIET = False


def _log(*args, **kwargs):
    if not _QUIET:
        print(*args, **kwargs)


# ── 0x55 protocol (from APK decompilation: Nothing Ear 3 / Donphan) ────────────
#
# Frame layout (both directions):
#   [SOF:1=0x55][ctrl:2 LE][cmd:2 LE][len:2 LE][fsn:1][payload:len][crc:2 if ctrl&0x20]
#
# All outgoing frames use ctrl=0x0160 with CRC16-ARC appended.
# APK: sendDataNeedCrc()=true for all commands; device silently drops SETs if any
# non-CRC frames were sent in the session.
#
# TX: send raw 16-bit cmd ID as-is (bit 15 preserved).
# RX: device sends responses with bit 15 cleared; normalize: received_cmd | 0x8000.
#
# CRC covers: SOF + ctrl(2) + cmd(2) + len(2) + FSN + payload
# CRC16-IBM/ARC: init=0xFFFF, poly=0xA001 (reflected 0x8005)

_SOF = 0x55
_CTRL_HOST_CRC = 0x0160  # all outgoing frames: CRC + multiFrames + deviceType=1

# Query commands (0xC0xx) – app→device, response has bit15 cleared
_CMD_PROTO_VERSION = 0xC001  # activation handshake (isNeedActivate=true)
_CMD_REMOTE_CONF = 0xC006  # GET_REMOTE_CONFIGURATION — serial number (UTF-8 string)
_CMD_BATTERY = 0xC007
_CMD_EARPHONE = 0xC00A
_CMD_NOISE_RED = 0xC01E  # get ANC state; payload [0x03] = request 3 entries
_CMD_EQ_MODE = 0xC01F
_CMD_HOST_VERSION = 0xC042  # GET_HOST_VERSION_DEVICE — firmware version (UTF-8 string)

# SET commands (0xF0xx) – app→device, ACK has bit15 cleared
_CMD_SET_ACTIVATED = 0xF001  # activation response; no payload
_CMD_SET_NOISE_RED = 0xF00F  # payload: [0x01, anc_val, 0x00]
_CMD_SET_EQ = 0xF010  # payload: [eq_val]


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b & 0xFF
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
    return crc & 0xFFFF


# Device event notifications (0xE0xx) – device→app, bit15 always set
_EVT_BATTERY = 0xE001
_EVT_STATUS = 0xE002
_EVT_NOISE_RED = 0xE003

# Battery payload: [type:1][val:1] pairs
#   type 2=left  3=right  4=case
#   val: bit7=charging, bits[6:0]=percent
_BAT_LEFT = 2
_BAT_RIGHT = 3
_BAT_CASE = 4

# ANC wire values for SET_NOISE_RED payload byte [1] (type=1 = NOISE_REDUCTION_MODE triplet)
# These are MODE constants from DeviceNoiseReduction.java, NOT the VALUE constants.
# VALUE_NOISE_REDUCTION_CLOSE=0 and VALUE_PASS_THROUGH=0xFE are for type=2 (level) entries.
_ANC_OFF = 5  # MODE_NOISE_REDUCTION_CLOSE
_ANC_STRONG = 1  # MODE_NOISE_REDUCTION_STRONG  (confirmed working)
_ANC_MEDIUM = 2  # MODE_NOISE_REDUCTION_MEDIUM
_ANC_WEAK = 3  # MODE_NOISE_REDUCTION_WEAK
_ANC_TRANSPARENCY = 7  # MODE_PASS_THROUGH

# ── Legacy 0x03/0x02 protocol (ch17 status-only stream) ──────────────────────
# Still used for battery parsing from the old status channel fallback.
_L_DEV_HDR = 0x03
_L_HOST_HDR = 0x02
_L_INIT = 0x01  # init handshake, echo back
_L_STATE = 0x02
_L_BATTERY = 0x03

# ── Channel probe priority ───────────────────────────────────────────────────
_PROBE_CHANNELS = [15, 17, 16, 18, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]


# ── Public enumerations ──────────────────────────────────────────────────────


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
    # None = not yet determined (show all); frozenset = confirmed supported modes
    supported_anc_modes: frozenset | None = None


# ── Device class ─────────────────────────────────────────────────────────────


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
        self._fsn = 0
        self._activated = False
        self._anc_debounce_id: int | None = None
        self._anc_pending_mode: int = ANCMode.OFF
        self._last_anc_level: int = _ANC_STRONG
        self._thread: threading.Thread | None = None
        self._low_bat_notified: dict[str, set[int]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def connect_rfcomm(self):
        if self._thread and self._thread.is_alive():
            return

        def _run():
            channels = self._discover_channels()
            for ch in channels:
                result = self._try_channel(ch)
                if result is None:
                    continue
                sock, initial = result
                self._sock = sock
                self._rfcomm_connected = True
                _log(f"[protocol] using ch{ch}")
                GLib.idle_add(self.emit, "connected")
                # The probe already sent GET_PROTOCOL_VERSION; the response is
                # in `initial` and will trigger activation + queries inside recv_loop.
                self._recv_loop(initial)
                return
            _log(
                f"[protocol] no responsive channel found for {self.address}\n"
                "[protocol] tip: sudo usermod -aG bluetooth $USER and re-login"
            )

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def disconnect_rfcomm(self):
        self._rfcomm_connected = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
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
        GLib.idle_add(self.emit, "state-changed")
        if self._anc_debounce_id is not None:
            GLib.source_remove(self._anc_debounce_id)
        self._anc_pending_mode = mode
        self._anc_debounce_id = GLib.timeout_add(300, self._do_set_anc)
        from . import profiles

        profiles.save(self.address, mode, self.state.eq_preset)

    def _do_set_anc(self):
        self._anc_debounce_id = None
        if not self._activated:
            return False
        mode = self._anc_pending_mode
        val = (
            _ANC_TRANSPARENCY
            if mode == ANCMode.TRANSPARENCY
            else (_ANC_OFF if mode == ANCMode.OFF else _ANC_STRONG)
        )
        label = ANCMode.LABELS.get(mode, mode)
        self._x55_send(_CMD_SET_NOISE_RED, bytes([0x01, val, 0x00]), label=f"ANC={label}")
        return False

    def set_eq_preset(self, preset: str):
        self.state.eq_preset = preset
        GLib.idle_add(self.emit, "state-changed")
        if not self._activated:
            return
        eq_val = EQ_PRESETS.get(preset, 0)
        self._x55_send(_CMD_SET_EQ, bytes([eq_val]), label=f"EQ={preset}")
        from . import profiles

        profiles.save(self.address, self.state.anc_mode, preset)

    def set_in_ear_detection(self, enabled: bool):
        self.state.in_ear_detection = enabled
        GLib.idle_add(self.emit, "state-changed")

    # ── Channel discovery ─────────────────────────────────────────────────────

    def _discover_channels(self) -> list[int]:
        try:
            import bluetooth as pybluez  # type: ignore

            services = pybluez.find_service(address=self.address)
            channels = [s["port"] for s in services if isinstance(s.get("port"), int)]
            if channels:
                _log(f"[protocol] PyBluez SDP channels: {channels}")
                return _prioritise(channels)
        except ImportError:
            _log("[protocol] PyBluez not installed; falling back to channel probe")
        except Exception as exc:
            _log(f"[protocol] PyBluez SDP failed: {exc}")

        try:
            out = subprocess.run(
                ["sdptool", "browse", self.address],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            channels = []
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Channel:"):
                    try:
                        channels.append(int(line.split(":")[1].strip()))
                    except ValueError:
                        pass
            if channels:
                _log(f"[protocol] sdptool channels: {channels}")
                return _prioritise(channels)
            _log("[protocol] sdptool returned no channels")
        except FileNotFoundError:
            _log("[protocol] sdptool not found; install bluez-utils or python-pybluez")
        except Exception as exc:
            _log(f"[protocol] sdptool failed: {exc}")

        _log(f"[protocol] probing channels {_PROBE_CHANNELS}")
        return _PROBE_CHANNELS

    def _try_channel(self, ch: int) -> tuple[socket.socket, bytes] | None:
        for attempt in range(2):
            try:
                sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                sock.settimeout(5)
                sock.connect((self.address, ch))
                break
            except OSError as exc:
                import errno as _errno

                if exc.errno == _errno.EBUSY and attempt == 0:
                    _log(f"[protocol] ch{ch}: busy — waiting 3s for stale connection to release")
                    sock.close()
                    time.sleep(3)
                    continue
                _log(f"[protocol] ch{ch}: connect failed: {exc}")
                return None
        else:
            return None

        # Probe with GET_PROTOCOL_VERSION — use CRC to match official app (sendDataNeedCrc=true)
        _probe_hdr = struct.pack("<BHHH", _SOF, _CTRL_HOST_CRC, _CMD_PROTO_VERSION, 0) + bytes([0x01])
        probe_x55 = _probe_hdr + struct.pack("<H", _crc16(_probe_hdr))
        probe_leg = bytes([_L_HOST_HDR, _L_BATTERY, 0x00, 0x00])
        try:
            sock.sendall(probe_x55 + probe_leg)
        except OSError:
            sock.close()
            return None

        sock.settimeout(2.0)
        data = b""
        deadline = time.monotonic() + 2.0
        try:
            while time.monotonic() < deadline:
                chunk = sock.recv(256)
                if not chunk:
                    break
                data += chunk
                if len(data) >= 4:
                    break
        except TimeoutError:
            pass

        if not data:
            _log(f"[protocol] ch{ch}: no response (skipping)")
            sock.close()
            return None

        proto = (
            "0x55" if data[0] == _SOF else ("0x03-legacy" if data[0] == _L_DEV_HDR else f"0x{data[0]:02x}")
        )
        _log(f"[protocol] ch{ch}: {proto} — {data.hex()}")
        sock.settimeout(6)
        return sock, data

    # ── Receive loop ──────────────────────────────────────────────────────────

    def _recv_loop(self, initial: bytes = b""):
        buf = initial
        if buf:
            buf = self._process_buf(buf)
        while self._rfcomm_connected and self._sock:
            try:
                chunk = self._sock.recv(256)
                if not chunk:
                    break
                if _DEBUG:
                    _log(f"[RX RAW] {chunk.hex()}")
                buf += chunk
                buf = self._process_buf(buf)
            except TimeoutError:
                continue
            except OSError:
                break
        self._handle_disconnect()

    def _process_buf(self, buf: bytes) -> bytes:
        while buf:
            if buf[0] == _SOF:
                buf = self._process_x55(buf)
                if not buf or buf[0] == _SOF:
                    continue
            if buf and buf[0] == _L_DEV_HDR:
                buf = self._process_legacy(buf)
                if not buf or buf[0] == _L_DEV_HDR:
                    continue
            if buf:
                buf = buf[1:]  # skip unknown byte
        return buf

    # ── 0x55 frame handling ───────────────────────────────────────────────────

    def _x55_send(self, cmd_id: int, payload: bytes = b"", *, label: str = ""):
        if not self._rfcomm_connected or not self._sock:
            return
        self._fsn = (self._fsn + 1) & 0xFF
        header = struct.pack("<BHHH", _SOF, _CTRL_HOST_CRC, cmd_id, len(payload)) + bytes([self._fsn])
        frame = header + payload + struct.pack("<H", _crc16(header + payload))
        desc = f" ({label})" if label else f" {payload.hex()}" if payload else ""
        _log(f"[TX] cmd=0x{cmd_id:04X}{desc}")
        if _DEBUG:
            _log(f"[TX RAW] {frame.hex()}")
        try:
            self._sock.sendall(frame)
        except OSError as exc:
            _log(f"[TX ERR] {exc}")
            self._handle_disconnect()

    def _process_x55(self, buf: bytes) -> bytes:
        while buf and buf[0] == _SOF:
            if len(buf) < 8:
                break
            _, ctrl, cmd_raw, length = struct.unpack_from("<BHHH", buf)
            # ctrl bit 5 = CRC flag: device appends 2 CRC bytes after payload
            crc_size = 2 if (ctrl & 0x20) else 0
            total = 8 + length + crc_size
            if len(buf) < total:
                break
            if crc_size:
                rx_crc = struct.unpack_from("<H", buf, 8 + length)[0]
                ok_crc = _crc16(buf[: 8 + length])
                if rx_crc != ok_crc:
                    _log(f"[RX CRC ERR] got 0x{rx_crc:04X} expected 0x{ok_crc:04X}")
            payload = buf[8 : 8 + length]
            cmd_id = cmd_raw | 0x8000  # normalize response→request ID
            self._dispatch_x55(cmd_id, payload)
            buf = buf[total:]
        return buf

    def _dispatch_x55(self, cmd_id: int, payload: bytes):
        changed = False
        if cmd_id == _CMD_PROTO_VERSION:
            ver = payload.decode(errors="replace").strip()
            _log(f"[RX INFO] proto version={ver!r}")
            self._x55_send(_CMD_SET_ACTIVATED)
            GLib.timeout_add(3000, self._activation_fallback)
        elif cmd_id == _CMD_SET_ACTIVATED:
            _log(f"[RX INFO] activation ACK payload={payload.hex()}")
            if not self._activated:
                GLib.timeout_add(2000, self._poll_earphone_status)
            self._activated = True
            from . import profiles

            profiles.set_last_device(self.address)
            # Always resend on real ACK — fallback may have sent queries before
            # the device finished activating and silently dropped them.
            self._x55_send(_CMD_BATTERY)
            self._x55_send(_CMD_NOISE_RED, bytes([0x03]))
            self._x55_send(_CMD_EARPHONE)
            self._x55_send(_CMD_HOST_VERSION)
            self._x55_send(_CMD_REMOTE_CONF)
            self._restore_profile()
        elif cmd_id in (_CMD_BATTERY, _EVT_BATTERY):
            changed = self._parse_battery(payload)
        elif cmd_id in (_CMD_NOISE_RED, _EVT_NOISE_RED):
            changed = self._parse_anc(payload)
        elif cmd_id == _CMD_EARPHONE:
            changed = self._parse_earphone_status(payload)
        elif cmd_id == _EVT_STATUS:
            # The pushed event only carries accurate data for the bud that
            # changed; the other entries are stale placeholders. Use it purely
            # as a trigger and re-query for a fresh full snapshot.
            if _DEBUG:
                _log(f"[protocol] EVT_STATUS {payload.hex()} → re-query GET_EARPHONE")
            self._x55_send(_CMD_EARPHONE)
        elif cmd_id == _CMD_HOST_VERSION:
            ver = payload.decode(errors="replace").strip("\x00").strip()
            if ver and ver != self.state.firmware_version:
                self.state.firmware_version = ver
                _log(f"[protocol] firmware={ver!r}")
                changed = True
        elif cmd_id == _CMD_REMOTE_CONF:
            # Payload is newline-separated "device_id,field_id,value" entries.
            # field 4 = serial number (e.g. SH10212543006451)
            raw = payload.decode(errors="replace").strip("\x00")
            sn = None
            for line in raw.splitlines():
                parts = line.split(",", 2)
                if len(parts) == 3 and parts[1] == "4" and parts[2].strip():
                    sn = parts[2].strip()
                    break
            if sn and sn != self.state.serial_number:
                self.state.serial_number = sn
                _log(f"[protocol] serial={sn!r}")
                changed = True
        elif cmd_id == _CMD_SET_NOISE_RED:
            _log(f"[RX INFO] ANC set ACK: {payload.hex()}")
        elif cmd_id == _CMD_SET_EQ:
            _log(f"[RX INFO] EQ set ACK: {payload.hex()}")
        else:
            _log(f"[RX    ] cmd=0x{cmd_id:04X} payload={payload.hex()}")
        if changed:
            GLib.idle_add(self.emit, "state-changed")

    def _parse_battery(self, payload: bytes) -> bool:
        # payload: [count:1][type:1][val:1]... (DataExtKt.toPairs with leading count byte)
        # val byte: bit7=charging, bits[6:0]=percent
        if len(payload) < 3:
            return False
        count = payload[0]
        changed = False
        for i in range(1, 1 + count * 2, 2):
            if i + 1 >= len(payload):
                break
            btype = payload[i]
            bval = payload[i + 1]
            pct = bval & 0x7F
            if btype == _BAT_LEFT and pct != self.state.left_battery:
                self.state.left_battery = pct
                self._check_low_battery("left", pct, "Left earbud")
                changed = True
            elif btype == _BAT_RIGHT and pct != self.state.right_battery:
                self.state.right_battery = pct
                self._check_low_battery("right", pct, "Right earbud")
                changed = True
            elif btype == _BAT_CASE and pct != self.state.case_battery:
                self.state.case_battery = pct
                self._check_low_battery("case", pct, "Case")
                changed = True
        if changed:
            _log(
                f"[protocol] battery L={self.state.left_battery}% "
                f"R={self.state.right_battery}% C={self.state.case_battery}%"
            )
        return changed

    def _parse_anc(self, payload: bytes) -> bool:
        # Payload: [type:1][value:1][pad:1] triplets
        #   type=1: NOISE_REDUCTION_MODE  type=2: NOISE_REDUCTION_LEVEL (last active level)
        #   level val 1–4 = ANC strength → ANC is supported
        #   level val 0 or 0xFE = no ANC strength → only Off + Transparency
        if len(payload) < 3:
            return False
        changed = False
        level_val: int | None = None
        for i in range(0, len(payload) - 2, 3):
            t, val = payload[i], payload[i + 1]
            if t == 1:  # NOISE_REDUCTION_MODE
                if val == _ANC_TRANSPARENCY:
                    mode = ANCMode.TRANSPARENCY
                elif val == _ANC_OFF or val == 0:
                    mode = ANCMode.OFF
                else:
                    mode = ANCMode.NOISE_CANCELLATION
                if mode != self.state.anc_mode:
                    self.state.anc_mode = mode
                    _log(f"[protocol] ANC mode → {ANCMode.LABELS.get(mode, mode)} (wire val {val})")
                    changed = True
            elif t == 2:  # NOISE_REDUCTION_LEVEL
                level_val = val
                if 1 <= val <= 4:
                    self._last_anc_level = val

        # First time we see a level entry, lock in supported modes.
        # val 1–4 = ANC strength present → all three modes are available.
        # val 0 or 0xFE = no ANC strength → device only supports Off + Transparency.
        if level_val is not None and self.state.supported_anc_modes is None:
            if 1 <= level_val <= 4:
                modes = frozenset([ANCMode.OFF, ANCMode.NOISE_CANCELLATION, ANCMode.TRANSPARENCY])
            else:
                modes = frozenset([ANCMode.OFF, ANCMode.TRANSPARENCY])
            self.state.supported_anc_modes = modes
            _log(
                f"[protocol] supported ANC modes detected: {[ANCMode.LABELS.get(m, m) for m in sorted(modes)]}"
            )
            changed = True

        return changed

    def _parse_earphone_status(self, payload: bytes) -> bool:
        # payload: [count:1][type:1][val:1]...  (only GET responses reach here;
        # they are a fresh full snapshot, unlike the EVT push frames)
        # EarphoneStatus.java: bit0=inCase, bit2=inEar, bit7=isConnect
        # type: 2=left, 3=right, 4=case, 5=tws, 6=stereo
        if len(payload) < 3:
            return False
        count = payload[0]
        changed = False
        if _DEBUG:
            _log(f"[protocol] earphone raw={payload.hex()}")
        for i in range(1, 1 + count * 2, 2):
            if i + 1 >= len(payload):
                break
            etype = payload[i]
            val = payload[i + 1]
            if etype not in (2, 3):
                continue
            in_ear = bool(val & 0x04)
            if etype == 2 and in_ear != self.state.left_wearing:
                self.state.left_wearing = in_ear
                changed = True
            elif etype == 3 and in_ear != self.state.right_wearing:
                self.state.right_wearing = in_ear
                changed = True
        if changed:
            _log(f"[protocol] wearing L={self.state.left_wearing} R={self.state.right_wearing}")
        return changed

    # ── Legacy 0x03 frame handling (status-only fallback) ────────────────────

    def _process_legacy(self, buf: bytes) -> bytes:
        while buf and buf[0] == _L_DEV_HDR:
            if len(buf) < 4:
                break
            msg_type = buf[1]
            length = struct.unpack(">H", buf[2:4])[0]
            if len(buf) < 4 + length:
                break
            self._dispatch_legacy(msg_type, buf[4 : 4 + length])
            buf = buf[4 + length :]
        return buf

    def _dispatch_legacy(self, msg_type: int, payload: bytes):
        if msg_type == _L_BATTERY and len(payload) >= 2:
            self.state.left_battery = payload[0] if payload[0] <= 100 else -1
            self.state.right_battery = payload[1] if payload[1] <= 100 else -1
            self.state.case_battery = payload[2] if len(payload) >= 3 and payload[2] <= 100 else -1
            _log(
                f"[protocol] legacy battery L={self.state.left_battery}% "
                f"R={self.state.right_battery}% C={self.state.case_battery}%"
            )
            self._check_low_battery("left", self.state.left_battery, "Left earbud")
            self._check_low_battery("right", self.state.right_battery, "Right earbud")
            self._check_low_battery("case", self.state.case_battery, "Case")
            GLib.idle_add(self.emit, "state-changed")
        elif msg_type == _L_INIT and payload:
            _log(f"[protocol] legacy init: {payload.hex()} — echoing back")
            # Echo init to complete handshake
            frame = bytes([_L_HOST_HDR, _L_INIT]) + struct.pack(">H", len(payload)) + payload
            try:
                if self._sock:
                    self._sock.sendall(frame)
            except OSError:
                pass
        elif msg_type == _L_STATE and payload:
            _log(f"[protocol] legacy state: {payload.hex()}")
        else:
            _log(f"[protocol] legacy type=0x{msg_type:02x} payload={payload.hex()}")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _restore_profile(self):
        from . import profiles

        p = profiles.load(self.address)
        if not p:
            return
        if "anc" in p:
            anc = p["anc"]
            wire = (
                _ANC_TRANSPARENCY
                if anc == ANCMode.TRANSPARENCY
                else _ANC_OFF
                if anc == ANCMode.OFF
                else _ANC_STRONG
            )
            self._x55_send(
                _CMD_SET_NOISE_RED, bytes([0x01, wire, 0x00]), label=f"restore ANC={ANCMode.LABELS.get(anc)}"
            )
        if "eq" in p:
            eq_val = EQ_PRESETS.get(p["eq"], 0)
            self._x55_send(_CMD_SET_EQ, bytes([eq_val]), label=f"restore EQ={p['eq']}")

    _LOW_BAT_THRESHOLDS = (20, 15, 10, 5)

    def _check_low_battery(self, slot: str, pct: int, label: str):
        if pct < 0:
            return
        if pct > 25:
            self._low_bat_notified.pop(slot, None)
            return
        notified = self._low_bat_notified.setdefault(slot, set())
        for threshold in self._LOW_BAT_THRESHOLDS:
            if pct <= threshold and threshold not in notified:
                notified.add(threshold)
                threading.Thread(
                    target=subprocess.run,
                    args=(
                        [
                            "notify-send",
                            "-u",
                            "critical",
                            "-i",
                            "battery-caution",
                            "Something X",
                            f"{label}: {pct}% battery remaining",
                        ],
                    ),
                    kwargs={"capture_output": True},
                    daemon=True,
                ).start()
                break

    def _poll_earphone_status(self):
        # The firmware only computes a fresh per-bud snapshot when asked; the
        # pushed EVT frames carry stale placeholder entries for the bud that
        # didn't change. Polling keeps both buds' wearing state accurate.
        if not self._rfcomm_connected:
            return False
        self._x55_send(_CMD_EARPHONE)
        return True

    def _activation_fallback(self):
        if not self._activated and self._rfcomm_connected:
            _log("[protocol] activation ACK not received within 3s — sending GET queries")
            self._activated = True
            GLib.timeout_add(2000, self._poll_earphone_status)
            self._x55_send(_CMD_BATTERY)
            self._x55_send(_CMD_NOISE_RED, bytes([0x03]))
            self._x55_send(_CMD_EARPHONE)
            self._x55_send(_CMD_HOST_VERSION)
            self._x55_send(_CMD_REMOTE_CONF)
        return False

    def _handle_disconnect(self):
        self._rfcomm_connected = False
        self._sock = None
        self._activated = False
        GLib.idle_add(self.emit, "disconnected")


def _prioritise(channels: list[int]) -> list[int]:
    priority = [c for c in [15, 17, 16] if c in channels]
    rest = [c for c in channels if c not in priority]
    return priority + rest
