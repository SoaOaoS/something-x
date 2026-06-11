import os
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib, GObject

from .bluetooth import BluetoothManager, BluetoothDevice, device_icon_name

_ITEM_IFACE = "org.kde.StatusNotifierItem"
_WATCHER_IFACE = "org.kde.StatusNotifierWatcher"
_WATCHER_SERVICE = "org.kde.StatusNotifierWatcher"
_ITEM_PATH = "/StatusNotifierItem"

_EMPTY_PIXMAPS = dbus.Array([], signature="(iiay)")


class _SNIItem(dbus.service.Object):
    def __init__(self, bus, service_name, on_activate):
        bus_name = dbus.service.BusName(service_name, bus)
        super().__init__(bus_name, _ITEM_PATH)
        self._on_activate = on_activate
        self._icon_name = "audio-headphones"
        self._tooltip_title = "Something X"
        self._tooltip_body = ""

    # ── SNI methods ────────────────────────────────────────────────────────────

    @dbus.service.method(_ITEM_IFACE, in_signature="ii")
    def Activate(self, x, y):
        GLib.idle_add(self._on_activate)

    @dbus.service.method(_ITEM_IFACE, in_signature="ii")
    def SecondaryActivate(self, x, y):
        pass

    @dbus.service.method(_ITEM_IFACE, in_signature="ii")
    def ContextMenu(self, x, y):
        pass

    @dbus.service.method(_ITEM_IFACE, in_signature="is")
    def Scroll(self, delta, orientation):
        pass

    # ── SNI signals ───────────────────────────────────────────────────────────

    @dbus.service.signal(_ITEM_IFACE)
    def NewIcon(self):
        pass

    @dbus.service.signal(_ITEM_IFACE)
    def NewToolTip(self):
        pass

    @dbus.service.signal(_ITEM_IFACE, signature="s")
    def NewStatus(self, status):
        pass

    # ── D-Bus Properties ──────────────────────────────────────────────────────

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._props()[prop]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._props()

    def _props(self):
        tooltip = dbus.Struct(
            (
                dbus.String(""),
                _EMPTY_PIXMAPS,
                dbus.String(self._tooltip_title),
                dbus.String(self._tooltip_body),
            ),
            signature="sa(iiay)ss",
        )
        return {
            "Id": dbus.String("something-x"),
            "Category": dbus.String("Hardware"),
            "Title": dbus.String("Something X"),
            "Status": dbus.String("Active"),
            "WindowId": dbus.UInt32(0),
            "IconName": dbus.String(self._icon_name),
            "IconPixmap": _EMPTY_PIXMAPS,
            "OverlayIconName": dbus.String(""),
            "OverlayIconPixmap": _EMPTY_PIXMAPS,
            "AttentionIconName": dbus.String(""),
            "AttentionIconPixmap": _EMPTY_PIXMAPS,
            "AttentionMovieName": dbus.String(""),
            "ToolTip": tooltip,
            "ItemIsMenu": dbus.Boolean(False),
            "Menu": dbus.ObjectPath(_ITEM_PATH),
        }

    # ── update helpers ────────────────────────────────────────────────────────

    def set_icon(self, icon_name: str):
        if icon_name != self._icon_name:
            self._icon_name = icon_name
            self.NewIcon()

    def set_tooltip(self, title: str, body: str):
        self._tooltip_title = title
        self._tooltip_body = body
        self.NewToolTip()


class SomethingXTray(GObject.Object):
    """StatusNotifierItem tray icon. Shows battery on hover; icon adapts to device type."""

    def __init__(self, bt_manager: BluetoothManager, on_show_window):
        super().__init__()
        self._bt = bt_manager
        self._on_show = on_show_window
        self._item: _SNIItem | None = None
        self._setup()
        bt_manager.connect("devices-changed", self._on_devices_changed)

    def _setup(self):
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            service_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
            self._item = _SNIItem(bus, service_name, self._on_show)
            try:
                watcher = bus.get_object(_WATCHER_SERVICE, "/StatusNotifierWatcher")
                dbus.Interface(watcher, _WATCHER_IFACE).RegisterStatusNotifierItem(service_name)
            except dbus.exceptions.DBusException:
                pass  # watcher not running; item is still exported on the bus
        except Exception as exc:
            print(f"[tray] SNI setup failed: {exc}")

    def _on_devices_changed(self, _manager):
        if not self._item:
            return
        nothing_devs = self._bt.get_nothing_devices()
        connected = [d for d in nothing_devs if d.connected]
        if connected:
            dev = connected[0]
            parts = []
            if dev.battery is not None:
                parts.append(f"{dev.name}: {dev.battery}%")
            self._item.set_tooltip("Something X", "\n".join(parts) if parts else "Connected")
            self._item.set_icon(device_icon_name(dev))
        else:
            # fall back to first paired Nothing device, or generic icon
            paired = nothing_devs[0] if nothing_devs else None
            icon = device_icon_name(paired) if paired else "audio-headphones"
            self._item.set_tooltip("Something X", "No devices connected")
            self._item.set_icon(icon)
