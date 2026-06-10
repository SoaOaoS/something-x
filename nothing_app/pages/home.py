import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, GObject

from ..bluetooth import BluetoothDevice, BluetoothManager, device_icon_name


class DeviceRow(Gtk.Box):
    def __init__(self, device: BluetoothDevice, on_action=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.add_css_class("device-card")
        self.device = device
        self._on_action = on_action
        self._build()

    def _build(self):
        icon = Gtk.Image.new_from_icon_name(device_icon_name(self.device))
        icon.set_pixel_size(28)
        icon.set_opacity(0.6)
        self.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_lbl = Gtk.Label(label=self.device.name)
        name_lbl.add_css_class("device-card-name")
        name_lbl.set_xalign(0)
        name_row.append(name_lbl)

        if self.device.is_nothing:
            badge = Gtk.Label(label="NOTHING")
            badge.add_css_class("status-nothing")
            name_row.append(badge)

        text_box.append(name_row)

        addr_lbl = Gtk.Label(label=self.device.address)
        addr_lbl.add_css_class("device-card-address")
        addr_lbl.set_xalign(0)
        text_box.append(addr_lbl)

        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_lbl = Gtk.Label(label="● Connected" if self.device.connected else "○ Disconnected")
        status_lbl.add_css_class("status-connected" if self.device.connected else "status-disconnected")
        status_lbl.set_xalign(0)
        bottom_row.append(status_lbl)

        if self.device.battery is not None:
            bat_lbl = Gtk.Label(label=f"  {self.device.battery}%")
            bat_lbl.add_css_class("battery-pct")
            bat_lbl.set_opacity(0.6)
            bottom_row.append(bat_lbl)

        text_box.append(bottom_row)
        self.append(text_box)

        if self._on_action is not None:
            action_btn = Gtk.Button(label="DISCONNECT" if self.device.connected else "CONNECT")
            action_btn.add_css_class("disconnect-button" if self.device.connected else "connect-button")
            action_btn.add_css_class("row-action")
            action_btn.set_valign(Gtk.Align.CENTER)
            action_btn.connect("clicked", self._on_action_clicked)
            self.append(action_btn)
        else:
            arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
            arrow.set_opacity(0.3)
            self.append(arrow)

    def _on_action_clicked(self, btn: Gtk.Button):
        btn.set_sensitive(False)
        btn.set_label("…")
        self._on_action(self.device)


class HomePage(Gtk.Box):
    __gsignals__ = {
        "device-selected": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, bt_manager: BluetoothManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._bt = bt_manager
        self._scanning = False
        self._build()
        bt_manager.connect("devices-changed", self._on_devices_changed)
        self._refresh_list()

    def _build(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content.add_css_class("nothing-page")
        scroll.set_child(self._content)
        self.append(scroll)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_top(20)
        header_box.set_margin_bottom(4)

        dot = Gtk.Box()
        dot.add_css_class("nothing-dot")
        dot.set_valign(Gtk.Align.CENTER)
        header_box.append(dot)

        brand = Gtk.Label(label="Something X")
        brand.add_css_class("section-label")
        brand.set_margin_top(0)
        brand.set_margin_bottom(0)
        header_box.append(brand)
        self._content.append(header_box)

        self._nothing_label = Gtk.Label(label="MY DEVICES")
        self._nothing_label.add_css_class("section-label")
        self._nothing_label.set_xalign(0)
        self._content.append(self._nothing_label)

        self._nothing_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._content.append(self._nothing_list)

        self._other_label = Gtk.Label(label="OTHER DEVICES")
        self._other_label.add_css_class("section-label")
        self._other_label.set_xalign(0)
        self._content.append(self._other_label)

        self._other_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._content.append(self._other_list)

        self._empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._empty_box.set_margin_top(60)
        self._empty_box.set_halign(Gtk.Align.CENTER)

        empty_icon = Gtk.Image.new_from_icon_name("bluetooth-symbolic")
        empty_icon.set_pixel_size(48)
        empty_icon.set_opacity(0.15)
        self._empty_box.append(empty_icon)

        empty_title = Gtk.Label(label="NO DEVICES")
        empty_title.add_css_class("empty-title")
        self._empty_box.append(empty_title)

        empty_sub = Gtk.Label(label="Pair a device via Bluetooth settings")
        empty_sub.add_css_class("empty-subtitle")
        self._empty_box.append(empty_sub)

        self._content.append(self._empty_box)

        scan_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        scan_row.set_margin_top(28)
        scan_row.set_halign(Gtk.Align.CENTER)

        self._scan_btn = Gtk.Button(label="SCAN FOR DEVICES")
        self._scan_btn.add_css_class("scan-button")
        self._scan_btn.connect("clicked", self._on_scan_clicked)
        scan_row.append(self._scan_btn)
        self._content.append(scan_row)

        self._bt_warning = Gtk.Label(label="⚠  Bluetooth unavailable — is bluetoothd running?")
        self._bt_warning.add_css_class("empty-subtitle")
        self._bt_warning.set_margin_top(8)
        self._bt_warning.set_halign(Gtk.Align.CENTER)
        self._content.append(self._bt_warning)
        self._bt_warning.set_visible(not self._bt.available)

    def _clear_list(self, box: Gtk.Box):
        while True:
            child = box.get_first_child()
            if child is None:
                break
            box.remove(child)

    def _refresh_list(self):
        devices = self._bt.get_all()
        nothing = [d for d in devices if d.is_nothing]
        others = [d for d in devices if not d.is_nothing]

        self._clear_list(self._nothing_list)
        self._clear_list(self._other_list)

        for dev in nothing:
            self._nothing_list.append(self._make_row(dev))

        for dev in others:
            self._other_list.append(self._make_row(dev))

        self._nothing_label.set_visible(bool(nothing))
        self._other_label.set_visible(bool(others))
        self._empty_box.set_visible(not devices)

    def _make_row(self, device: BluetoothDevice) -> Gtk.Widget:
        # Only Nothing devices have a detail page; other devices get an inline
        # connect/disconnect button instead of navigation.
        if not device.is_nothing:
            return DeviceRow(device, on_action=self._on_quick_action)
        btn = Gtk.Button()
        btn.set_has_frame(False)
        btn.add_css_class("device-row-btn")
        row = DeviceRow(device)
        btn.set_child(row)
        btn.connect("clicked", lambda _b, d=device: self.emit("device-selected", d))
        return btn

    def _on_quick_action(self, device: BluetoothDevice):
        if device.connected:
            self._bt.disconnect_device(device.path)
        else:
            self._bt.connect_device(device.path, on_error=self._refresh_list)

    def _on_devices_changed(self, _manager):
        self._refresh_list()

    def _on_scan_clicked(self, _btn):
        if self._scanning:
            return
        self._scanning = True
        self._scan_btn.set_label("SCANNING…")
        self._scan_btn.set_sensitive(False)
        self._bt.start_discovery()
        GLib.timeout_add_seconds(30, self._scan_done)

    def _scan_done(self):
        self._scanning = False
        self._scan_btn.set_label("SCAN FOR DEVICES")
        self._scan_btn.set_sensitive(True)
        self._refresh_list()
        return False
