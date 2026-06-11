from gi.repository import Gio, GLib, GObject

BLUEZ_SERVICE = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"
BATTERY_IFACE = "org.bluez.Battery1"
OBJ_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

NOTHING_PATTERNS = (
    "nothing ear",
    "ear (1)",
    "ear (2)",
    "ear (a)",
    "ear (stick)",
    "cmf buds",
    "cmf earphone",
    "nothing phone",
)

# Lightweight proxy flags: no property caching, no auto-signal wiring.
# Used for proxies that only need to call methods.
_FLAGS_METHOD = Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES | Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS


class BluetoothDevice:
    def __init__(self, path: str, props: dict):
        self.path = path
        self.address: str = str(props.get("Address", ""))
        self.name: str = str(props.get("Name", props.get("Alias", "Unknown Device")))
        self.connected: bool = bool(props.get("Connected", False))
        self.paired: bool = bool(props.get("Paired", False))
        self.battery: int | None = None
        self.icon: str = str(props.get("Icon", "audio-headphones"))
        self.is_nothing: bool = any(p in self.name.lower() for p in NOTHING_PATTERNS)

    def update(self, changed: dict):
        if "Connected" in changed:
            self.connected = bool(changed["Connected"])
        if "Name" in changed:
            self.name = str(changed["Name"])
        if "Alias" in changed and not self.name:
            self.name = str(changed["Alias"])

    def __repr__(self):
        return f"<BTDevice {self.name!r} {'●' if self.connected else '○'}>"


# BlueZ Device1.Icon → GTK symbolic icon name
_BLUEZ_ICON_MAP: dict[str, str] = {
    "audio-headphones": "audio-headphones-symbolic",
    "audio-headset": "audio-headset-symbolic",
    "audio-card": "audio-card-symbolic",
    "input-mouse": "input-mouse-symbolic",
    "input-keyboard": "input-keyboard-symbolic",
    "input-gaming": "input-gaming-symbolic",
    "input-tablet": "input-tablet-symbolic",
    "phone": "phone-symbolic",
    "computer": "computer-symbolic",
    "printer": "printer-symbolic",
}

_WATCH_NAME_PATTERNS = ("watch", "band", "gear", "amazfit", "fenix", "vivoactive", "galaxy fit")


def device_icon_name(device: "BluetoothDevice | None") -> str:
    """Return a GTK symbolic icon name for a Bluetooth device."""
    if device is None:
        return "audio-headphones-symbolic"
    name_lower = device.name.lower()
    if any(p in name_lower for p in _WATCH_NAME_PATTERNS):
        return "alarm-symbolic"
    if "ear (stick)" in name_lower:
        return "audio-input-microphone-symbolic"
    mapped = _BLUEZ_ICON_MAP.get(device.icon)
    if mapped:
        return mapped
    if "phone" in name_lower:
        return "phone-symbolic"
    return "audio-headphones-symbolic"


class BluetoothManager(GObject.Object):
    __gsignals__ = {
        "devices-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "device-connected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "device-disconnected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.devices: dict[str, BluetoothDevice] = {}
        self._connection: Gio.DBusConnection | None = None
        self._adapter_path: str | None = None
        self._subs: list[int] = []
        self._available = False
        self._init_dbus()

    def _init_dbus(self):
        try:
            self._connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            mgr = Gio.DBusProxy.new_sync(
                self._connection,
                _FLAGS_METHOD,
                None,
                BLUEZ_SERVICE,
                "/",
                OBJ_MANAGER_IFACE,
                None,
            )
            # Non-blocking: populates devices and emits devices-changed when ready
            mgr.call(
                "GetManagedObjects",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_managed_objects,
                None,
            )
            self._subscribe()
        except Exception as exc:
            print(f"[bluetooth] D-Bus init failed: {exc}")

    def _on_managed_objects(self, proxy, result, _user_data):
        try:
            variant = proxy.call_finish(result)
            objects = variant.unpack()[0]
            self._populate(objects)
            self._available = True
            GLib.idle_add(self.emit, "devices-changed")
        except Exception as exc:
            print(f"[bluetooth] GetManagedObjects failed: {exc}")

    def _populate(self, objects: dict):
        self.devices = {}
        self._adapter_path = None
        for path, ifaces in objects.items():
            if ADAPTER_IFACE in ifaces and self._adapter_path is None:
                self._adapter_path = path
            if DEVICE_IFACE not in ifaces:
                continue
            props = dict(ifaces[DEVICE_IFACE])
            dev = BluetoothDevice(path, props)
            if BATTERY_IFACE in ifaces:
                dev.battery = int(ifaces[BATTERY_IFACE].get("Percentage", 0))
            self.devices[path] = dev

    def _subscribe(self):
        if not self._connection:
            return
        try:
            self._subs.append(
                self._connection.signal_subscribe(
                    BLUEZ_SERVICE,
                    PROPERTIES_IFACE,
                    "PropertiesChanged",
                    None,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_props_changed,
                    None,
                )
            )
            self._subs.append(
                self._connection.signal_subscribe(
                    BLUEZ_SERVICE,
                    OBJ_MANAGER_IFACE,
                    "InterfacesAdded",
                    None,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_ifaces_added,
                    None,
                )
            )
            self._subs.append(
                self._connection.signal_subscribe(
                    BLUEZ_SERVICE,
                    OBJ_MANAGER_IFACE,
                    "InterfacesRemoved",
                    None,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_ifaces_removed,
                    None,
                )
            )
        except Exception as exc:
            print(f"[bluetooth] Signal subscribe failed: {exc}")

    def _on_props_changed(self, _conn, _sender, path, _iface, _signal, params, _user_data):
        iface_name, changed, _invalidated = params.unpack()
        if iface_name != DEVICE_IFACE:
            return
        if path not in self.devices:
            return
        dev = self.devices[path]
        old_connected = dev.connected
        dev.update(dict(changed))
        if dev.connected != old_connected:
            sig = "device-connected" if dev.connected else "device-disconnected"
            GLib.idle_add(self.emit, sig, path)
        GLib.idle_add(self.emit, "devices-changed")

    def _on_ifaces_added(self, _conn, _sender, _path, _iface, _signal, params, _user_data):
        obj_path, ifaces = params.unpack()
        if ADAPTER_IFACE in ifaces and self._adapter_path is None:
            self._adapter_path = obj_path
        if DEVICE_IFACE not in ifaces:
            return
        props = dict(ifaces[DEVICE_IFACE])
        dev = BluetoothDevice(obj_path, props)
        if BATTERY_IFACE in ifaces:
            dev.battery = int(ifaces[BATTERY_IFACE].get("Percentage", 0))
        self.devices[obj_path] = dev
        GLib.idle_add(self.emit, "devices-changed")

    def _on_ifaces_removed(self, _conn, _sender, _path, _iface, _signal, params, _user_data):
        obj_path, ifaces = params.unpack()
        if DEVICE_IFACE in ifaces and obj_path in self.devices:
            del self.devices[obj_path]
            GLib.idle_add(self.emit, "devices-changed")

    @property
    def available(self) -> bool:
        return self._available

    def get_all(self) -> list[BluetoothDevice]:
        return sorted(self.devices.values(), key=lambda d: (not d.connected, d.name))

    def get_nothing_devices(self) -> list[BluetoothDevice]:
        return [d for d in self.get_all() if d.is_nothing]

    def refresh(self):
        if not self._connection:
            return
        try:
            mgr = Gio.DBusProxy.new_sync(
                self._connection,
                _FLAGS_METHOD,
                None,
                BLUEZ_SERVICE,
                "/",
                OBJ_MANAGER_IFACE,
                None,
            )
            mgr.call(
                "GetManagedObjects",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_managed_objects,
                None,
            )
        except Exception as exc:
            print(f"[bluetooth] refresh: {exc}")

    def connect_device(self, path: str, on_error=None):
        if not self._connection:
            return
        Gio.DBusProxy.new(
            self._connection,
            _FLAGS_METHOD,
            None,
            BLUEZ_SERVICE,
            path,
            DEVICE_IFACE,
            None,
            self._on_connect_proxy_ready,
            on_error,
        )

    def _on_connect_proxy_ready(self, _source, result, on_error):
        try:
            proxy = Gio.DBusProxy.new_finish(result)
            proxy.call(
                "Connect",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_connect_done,
                on_error,
            )
        except Exception as exc:
            print(f"[bluetooth] connect proxy failed: {exc}")
            if on_error:
                GLib.idle_add(on_error)

    def _on_connect_done(self, proxy, result, on_error):
        try:
            proxy.call_finish(result)
        except Exception as exc:
            print(f"[BT] connect error: {exc}")
            if on_error:
                GLib.idle_add(on_error)

    def disconnect_device(self, path: str):
        if not self._connection:
            return
        Gio.DBusProxy.new(
            self._connection,
            _FLAGS_METHOD,
            None,
            BLUEZ_SERVICE,
            path,
            DEVICE_IFACE,
            None,
            self._on_disconnect_proxy_ready,
            None,
        )

    def _on_disconnect_proxy_ready(self, _source, result, _user_data):
        try:
            proxy = Gio.DBusProxy.new_finish(result)
            proxy.call(
                "Disconnect",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_disconnect_done,
                None,
            )
        except Exception as exc:
            print(f"[bluetooth] disconnect proxy failed: {exc}")

    def _on_disconnect_done(self, proxy, result, _user_data):
        try:
            proxy.call_finish(result)
        except Exception as exc:
            print(f"[BT] disconnect error: {exc}")

    def start_discovery(self):
        if not self._connection or not self._adapter_path:
            return
        try:
            proxy = Gio.DBusProxy.new_sync(
                self._connection,
                _FLAGS_METHOD,
                None,
                BLUEZ_SERVICE,
                self._adapter_path,
                ADAPTER_IFACE,
                None,
            )
            proxy.call(
                "StartDiscovery",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self._on_start_discovery_done,
                None,
            )
        except Exception as exc:
            print(f"[bluetooth] discovery start: {exc}")

    def _on_start_discovery_done(self, proxy, result, _user_data):
        try:
            proxy.call_finish(result)
            GLib.timeout_add_seconds(30, self._stop_discovery)
        except Exception as exc:
            print(f"[bluetooth] start discovery error: {exc}")

    def _stop_discovery(self):
        if not self._connection or not self._adapter_path:
            return False
        try:
            proxy = Gio.DBusProxy.new_sync(
                self._connection,
                _FLAGS_METHOD,
                None,
                BLUEZ_SERVICE,
                self._adapter_path,
                ADAPTER_IFACE,
                None,
            )
            proxy.call_sync("StopDiscovery", None, Gio.DBusCallFlags.NONE, -1, None)
        except Exception:
            pass
        return False
