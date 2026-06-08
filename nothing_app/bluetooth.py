import dbus
import dbus.mainloop.glib
from gi.repository import GLib, GObject

BLUEZ_SERVICE = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"
BATTERY_IFACE = "org.bluez.Battery1"
OBJ_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

NOTHING_PATTERNS = (
    "nothing ear", "ear (1)", "ear (2)", "ear (a)", "ear (stick)",
    "cmf buds", "cmf earphone", "nothing phone",
)


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


class BluetoothManager(GObject.Object):
    __gsignals__ = {
        "devices-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "device-connected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "device-disconnected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.devices: dict[str, BluetoothDevice] = {}
        self._bus: dbus.SystemBus | None = None
        self._available = False
        self._init_dbus()

    def _init_dbus(self):
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SystemBus()
            self._refresh()
            self._subscribe()
            self._available = True
        except Exception as exc:
            print(f"[bluetooth] D-Bus init failed: {exc}")

    def _refresh(self):
        if not self._bus:
            return
        try:
            mgr = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, "/"),
                OBJ_MANAGER_IFACE,
            )
            objects = mgr.GetManagedObjects()
            self.devices = {}
            for path, ifaces in objects.items():
                if DEVICE_IFACE not in ifaces:
                    continue
                props = {str(k): v for k, v in ifaces[DEVICE_IFACE].items()}
                dev = BluetoothDevice(str(path), props)
                if BATTERY_IFACE in ifaces:
                    dev.battery = int(ifaces[BATTERY_IFACE].get("Percentage", 0))
                self.devices[str(path)] = dev
        except Exception as exc:
            print(f"[bluetooth] Refresh failed: {exc}")

    def _subscribe(self):
        if not self._bus:
            return
        try:
            self._bus.add_signal_receiver(
                self._on_props_changed,
                signal_name="PropertiesChanged",
                dbus_interface=PROPERTIES_IFACE,
                path_keyword="path",
            )
            self._bus.add_signal_receiver(
                self._on_ifaces_added,
                signal_name="InterfacesAdded",
                dbus_interface=OBJ_MANAGER_IFACE,
                bus_name=BLUEZ_SERVICE,
            )
            self._bus.add_signal_receiver(
                self._on_ifaces_removed,
                signal_name="InterfacesRemoved",
                dbus_interface=OBJ_MANAGER_IFACE,
                bus_name=BLUEZ_SERVICE,
            )
        except Exception as exc:
            print(f"[bluetooth] Signal subscribe failed: {exc}")

    def _on_props_changed(self, interface, changed, _invalidated, path):
        if interface != DEVICE_IFACE:
            return
        path = str(path)
        if path not in self.devices:
            return
        dev = self.devices[path]
        old_connected = dev.connected
        dev.update({str(k): v for k, v in changed.items()})
        if dev.connected != old_connected:
            sig = "device-connected" if dev.connected else "device-disconnected"
            GLib.idle_add(self.emit, sig, path)
        GLib.idle_add(self.emit, "devices-changed")

    def _on_ifaces_added(self, path, ifaces):
        if DEVICE_IFACE not in ifaces:
            return
        props = {str(k): v for k, v in ifaces[DEVICE_IFACE].items()}
        dev = BluetoothDevice(str(path), props)
        if BATTERY_IFACE in ifaces:
            dev.battery = int(ifaces[BATTERY_IFACE].get("Percentage", 0))
        self.devices[str(path)] = dev
        GLib.idle_add(self.emit, "devices-changed")

    def _on_ifaces_removed(self, path, ifaces):
        path = str(path)
        if DEVICE_IFACE in ifaces and path in self.devices:
            del self.devices[path]
            GLib.idle_add(self.emit, "devices-changed")

    @property
    def available(self) -> bool:
        return self._available

    def get_all(self) -> list[BluetoothDevice]:
        return sorted(self.devices.values(), key=lambda d: (not d.connected, d.name))

    def get_nothing_devices(self) -> list[BluetoothDevice]:
        return [d for d in self.get_all() if d.is_nothing]

    def refresh(self):
        self._refresh()
        self.emit("devices-changed")

    def connect_device(self, path: str):
        if not self._bus:
            return
        try:
            iface = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path), DEVICE_IFACE
            )
            iface.Connect(
                reply_handler=lambda: None,
                error_handler=lambda e: print(f"[BT] connect error: {e}"),
            )
        except Exception as exc:
            print(f"[bluetooth] connect {path}: {exc}")

    def disconnect_device(self, path: str):
        if not self._bus:
            return
        try:
            iface = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path), DEVICE_IFACE
            )
            iface.Disconnect(
                reply_handler=lambda: None,
                error_handler=lambda e: print(f"[BT] disconnect error: {e}"),
            )
        except Exception as exc:
            print(f"[bluetooth] disconnect {path}: {exc}")

    def start_discovery(self):
        if not self._bus:
            return
        try:
            mgr = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, "/"), OBJ_MANAGER_IFACE
            )
            for path, ifaces in mgr.GetManagedObjects().items():
                if ADAPTER_IFACE in ifaces:
                    adapter = dbus.Interface(
                        self._bus.get_object(BLUEZ_SERVICE, path), ADAPTER_IFACE
                    )
                    adapter.StartDiscovery()
                    GLib.timeout_add_seconds(30, self._stop_discovery_on_path, str(path))
                    break
        except Exception as exc:
            print(f"[bluetooth] discovery start: {exc}")

    def _stop_discovery_on_path(self, path: str):
        try:
            adapter = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path), ADAPTER_IFACE
            )
            adapter.StopDiscovery()
        except Exception:
            pass
        return False
