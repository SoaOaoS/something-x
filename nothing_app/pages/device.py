import math
import re
import subprocess
import threading
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, GLib, PangoCairo

from ..bluetooth import BluetoothDevice, BluetoothManager


def _mono_font() -> str:
    available = {f.get_name() for f in PangoCairo.FontMap.get_default().list_families()}
    for name in ("JetBrainsMono", "Fira Mono", "DejaVu Sans Mono"):
        if name in available:
            return name
    return "monospace"


_MONO = _mono_font()
from ..protocol import NothingDevice, ANCMode, EQ_PRESETS


def _find_bt_sink(address: str) -> str | None:
    addr_key = address.replace(":", "_").lower()
    try:
        out = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
        for line in out.splitlines():
            if addr_key in line.lower():
                parts = line.split("\t")
                if len(parts) >= 2:
                    return parts[1].strip()
    except Exception:
        pass
    return None


def _get_sink_volume(address: str) -> int | None:
    sink = _find_bt_sink(address)
    if not sink:
        return None
    try:
        out = subprocess.run(
            ["pactl", "get-sink-volume", sink],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
        m = re.search(r"(\d+)%", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _set_sink_volume(address: str, pct: int):
    sink = _find_bt_sink(address)
    if not sink:
        return
    try:
        subprocess.run(
            ["pactl", "set-sink-volume", sink, f"{pct}%"],
            capture_output=True,
            timeout=2,
        )
    except Exception:
        pass


def _battery_color(pct: int) -> tuple[float, float, float]:
    if pct < 0:
        return (0.18, 0.18, 0.18)
    if pct <= 20:
        return (0.91, 0.32, 0.32)
    if pct <= 50:
        return (0.94, 0.75, 0.25)
    return (0.56, 0.87, 0.45)


class EarbudVisual(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(340, 190)
        self.set_draw_func(self._draw)
        self._left = -1
        self._right = -1
        self._case = -1
        self._left_wearing = False
        self._right_wearing = False

    def update(self, left: int, right: int, case: int, left_wearing: bool = False, right_wearing: bool = False):
        self._left, self._right, self._case = left, right, case
        self._left_wearing, self._right_wearing = left_wearing, right_wearing
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        cx = width / 2
        cy = height / 2 - 8
        self._draw_bud(cr, cx - 92, cy, self._left, "L", self._left_wearing)
        self._draw_bud(cr, cx + 92, cy, self._right, "R", self._right_wearing)
        self._draw_case(cr, cx, cy + 54, self._case)

    def _draw_bud(self, cr, cx, cy, pct, label, wearing: bool = False):
        R = 42
        r = 29
        bc = _battery_color(pct) if pct >= 0 else (0.18, 0.18, 0.18)

        # outer diffuse glow (battery color)
        for i in range(3):
            rg = cairo.RadialGradient(cx, cy, R - 2, cx, cy, R + 14 + i * 8)
            rg.add_color_stop_rgba(0, *bc, 0.10 - i * 0.025)
            rg.add_color_stop_rgba(1, *bc, 0)
            cr.set_source(rg)
            cr.arc(cx, cy, R + 14 + i * 8, 0, 2 * math.pi)
            cr.fill()

        # body: radial gradient for sphere depth
        body = cairo.RadialGradient(cx - R * 0.28, cy - R * 0.28, R * 0.08, cx, cy, R)
        body.add_color_stop_rgba(0, 0.24, 0.24, 0.24, 1.0)
        body.add_color_stop_rgba(0.7, 0.10, 0.10, 0.10, 1.0)
        body.add_color_stop_rgba(1, 0.04, 0.04, 0.04, 1.0)
        cr.set_source(body)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.fill()

        # battery track (dim full ring)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.07)
        cr.set_line_width(6)
        cr.arc(cx, cy, R - 3, 0, 2 * math.pi)
        cr.stroke()

        # battery arc (colored progress)
        if pct > 0:
            cr.set_source_rgba(*bc, 1.0)
            cr.set_line_width(6)
            cr.set_line_cap(cairo.LineCap.ROUND)
            cr.arc(cx, cy, R - 3, -math.pi / 2, -math.pi / 2 + (pct / 100) * 2 * math.pi)
            cr.stroke()

        # inner circle: radial gradient for glass depth
        inner = cairo.RadialGradient(cx - r * 0.32, cy - r * 0.32, r * 0.06, cx, cy, r)
        inner.add_color_stop_rgba(0, 0.17, 0.17, 0.17, 1.0)
        inner.add_color_stop_rgba(1, 0.03, 0.03, 0.03, 1.0)
        cr.set_source(inner)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

        # glass highlight arc (top-left crescent)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.10)
        cr.set_line_width(4)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.arc(cx, cy, r - 4, math.pi * 1.05, math.pi * 1.72)
        cr.stroke()

        # percentage text
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0 if pct >= 0 else 0.22)
        cr.select_font_face(_MONO, cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        text = f"{pct}%" if pct >= 0 else "—"
        cr.set_font_size(13 if pct >= 0 else 17)
        te = cr.text_extents(text)
        cr.move_to(cx - te.width / 2 - te.x_bearing, cy - te.height / 2 - te.y_bearing)
        cr.show_text(text)

        # in-ear indicator dot (always rendered; glows red when wearing)
        dot_y = cy + R + 8
        if wearing:
            rg = cairo.RadialGradient(cx, dot_y, 0, cx, dot_y, 9)
            rg.add_color_stop_rgba(0, 0.87, 0.18, 0.18, 0.30)
            rg.add_color_stop_rgba(1, 0.87, 0.18, 0.18, 0.0)
            cr.set_source(rg)
            cr.arc(cx, dot_y, 9, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgba(0.87, 0.18, 0.18, 0.9)
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.07)
        cr.arc(cx, dot_y, 3, 0, 2 * math.pi)
        cr.fill()

        # L / R label below
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.20)
        cr.select_font_face(_MONO, cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(9)
        te = cr.text_extents(label)
        cr.move_to(cx - te.width / 2 - te.x_bearing, cy + R + 20)
        cr.show_text(label)

    def _draw_case(self, cr, cx, cy, pct):
        R = 18
        bc = _battery_color(pct) if pct >= 0 else (0.18, 0.18, 0.18)

        # outer diffuse glow
        rg = cairo.RadialGradient(cx, cy, R - 1, cx, cy, R + 14)
        rg.add_color_stop_rgba(0, *bc, 0.09)
        rg.add_color_stop_rgba(1, *bc, 0)
        cr.set_source(rg)
        cr.arc(cx, cy, R + 14, 0, 2 * math.pi)
        cr.fill()

        # body
        body = cairo.RadialGradient(cx - R * 0.28, cy - R * 0.28, R * 0.08, cx, cy, R)
        body.add_color_stop_rgba(0, 0.22, 0.22, 0.22, 1.0)
        body.add_color_stop_rgba(1, 0.05, 0.05, 0.05, 1.0)
        cr.set_source(body)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.fill()

        # battery track
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.07)
        cr.set_line_width(4)
        cr.arc(cx, cy, R - 2, 0, 2 * math.pi)
        cr.stroke()

        # battery arc
        if pct > 0:
            cr.set_source_rgba(*bc, 1.0)
            cr.set_line_width(4)
            cr.set_line_cap(cairo.LineCap.ROUND)
            cr.arc(cx, cy, R - 2, -math.pi / 2, -math.pi / 2 + (pct / 100) * 2 * math.pi)
            cr.stroke()

        # glass highlight
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.09)
        cr.set_line_width(3)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.arc(cx, cy, R - 4, math.pi * 1.05, math.pi * 1.72)
        cr.stroke()

        # percentage text
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.72 if pct >= 0 else 0.20)
        cr.select_font_face(_MONO, cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        cr.set_font_size(9)
        text = f"{pct}%" if pct >= 0 else "—"
        te = cr.text_extents(text)
        cr.move_to(cx - te.width / 2 - te.x_bearing, cy - te.height / 2 - te.y_bearing)
        cr.show_text(text)

        # CASE label
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)
        cr.select_font_face(_MONO, cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(8)
        te = cr.text_extents("CASE")
        cr.move_to(cx - te.width / 2 - te.x_bearing, cy + R + 14)
        cr.show_text("CASE")


def _section(label: str) -> Gtk.Label:
    lbl = Gtk.Label(label=label)
    lbl.add_css_class("section-label")
    lbl.set_xalign(0)
    return lbl


def _settings_row(title: str, subtitle: str = "", right_widget: Gtk.Widget | None = None) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("settings-row")

    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text.set_hexpand(True)

    t = Gtk.Label(label=title)
    t.add_css_class("settings-row-title")
    t.set_xalign(0)
    text.append(t)

    if subtitle:
        s = Gtk.Label(label=subtitle)
        s.add_css_class("settings-row-subtitle")
        s.set_xalign(0)
        text.append(s)

    row.append(text)
    if right_widget:
        row.append(right_widget)
    return row


class DevicePage(Gtk.Box):
    def __init__(self, bt_device: BluetoothDevice, bt_manager: BluetoothManager, nothing_dev: NothingDevice | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._bt_device = bt_device
        self._bt = bt_manager
        self._nothing_dev: NothingDevice | None = None
        self._nd_handlers: list[int] = []
        self._anc_buttons: list[tuple[int, Gtk.Button]] = []
        self._eq_buttons: list[tuple[str, Gtk.Button]] = []
        self._updating_ui = False
        self._vol_debounce_id: int | None = None
        self._vol_handler: int | None = None
        self._bt_conn_handler = bt_manager.connect("device-connected", self._on_bt_device_connected)
        self._bt_disc_handler = bt_manager.connect("device-disconnected", self._on_bt_device_disconnected)
        self._connect_retries = 0
        self._connect_retry_id: int | None = None
        self._build()
        if bt_device.is_nothing:
            self._connect_nothing(nothing_dev)
        if bt_device.connected:
            GLib.timeout_add(800, self._query_volume)

    def _build(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.add_css_class("nothing-page")
        scroll.set_child(page)
        self.append(scroll)

        self._visual = EarbudVisual()
        self._visual.set_margin_top(16)
        self._visual.set_margin_bottom(8)
        page.append(self._visual)

        conn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        conn_box.set_halign(Gtk.Align.CENTER)
        conn_box.set_margin_bottom(4)

        self._conn_label = Gtk.Label()
        conn_box.append(self._conn_label)
        self._update_status_label()

        if self._bt_device.battery is not None:
            bat_lbl = Gtk.Label(label=f"  {self._bt_device.battery}%")
            bat_lbl.add_css_class("battery-pct")
            conn_box.append(bat_lbl)

        page.append(conn_box)

        if self._bt_device.is_nothing:
            self._build_nothing_controls(page)

        disc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        disc_row.set_halign(Gtk.Align.CENTER)
        disc_row.set_margin_top(24)
        disc_row.set_margin_bottom(8)

        self._conn_btn = Gtk.Button()
        self._update_conn_button()
        self._conn_btn.connect("clicked", self._on_conn_btn_clicked)
        disc_row.append(self._conn_btn)
        page.append(disc_row)

    def _build_nothing_controls(self, page: Gtk.Box):
        page.append(_section("SOUND MODE"))

        anc_outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        anc_outer.set_margin_bottom(4)
        anc_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        anc_container.add_css_class("anc-container")
        anc_container.set_hexpand(True)

        for mode, label in [
            (ANCMode.OFF, "Off"),
            (ANCMode.NOISE_CANCELLATION, "Noise Cancellation"),
            (ANCMode.TRANSPARENCY, "Transparency"),
        ]:
            btn = Gtk.Button(label=label)
            btn.add_css_class("anc-button")
            btn.set_hexpand(True)
            btn.connect("clicked", self._on_anc_clicked, mode)
            anc_container.append(btn)
            self._anc_buttons.append((mode, btn))

        anc_outer.append(anc_container)
        page.append(anc_outer)

        page.append(_section("EQUALIZER"))

        eq_flow = Gtk.FlowBox()
        eq_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        eq_flow.set_column_spacing(8)
        eq_flow.set_row_spacing(8)
        eq_flow.set_max_children_per_line(4)
        eq_flow.set_margin_bottom(4)

        for preset in EQ_PRESETS:
            btn = Gtk.Button(label=preset)
            btn.add_css_class("eq-button")
            btn.connect("clicked", self._on_eq_clicked, preset)
            eq_flow.append(btn)
            self._eq_buttons.append((preset, btn))

        page.append(eq_flow)

        page.append(_section("VOLUME"))

        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vol_row.set_margin_bottom(4)

        self._vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._vol_scale.set_hexpand(True)
        self._vol_scale.set_draw_value(False)
        self._vol_scale.add_css_class("volume-slider")
        self._vol_scale.set_value(70)
        self._vol_handler = self._vol_scale.connect("value-changed", self._on_volume_changed)

        self._vol_label = Gtk.Label(label="70%")
        self._vol_label.add_css_class("volume-label")
        self._vol_label.set_width_chars(4)
        self._vol_label.set_xalign(1)

        vol_row.append(self._vol_scale)
        vol_row.append(self._vol_label)
        page.append(vol_row)

        page.append(_section("SETTINGS"))

        settings_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        settings_group.add_css_class("settings-group")
        settings_group.set_margin_bottom(4)

        self._in_ear_switch = Gtk.Switch()
        self._in_ear_switch.set_active(True)
        self._in_ear_switch.set_valign(Gtk.Align.CENTER)
        self._in_ear_switch.connect("state-set", self._on_in_ear_toggled)
        settings_group.append(
            _settings_row(
                "In-Ear Detection",
                "Pause when earbuds are removed",
                self._in_ear_switch,
            )
        )

        self._auto_pause_switch = Gtk.Switch()
        self._auto_pause_switch.set_active(True)
        self._auto_pause_switch.set_valign(Gtk.Align.CENTER)
        settings_group.append(
            _settings_row(
                "Auto-Pause",
                "Pause media on removal",
                self._auto_pause_switch,
            )
        )

        page.append(settings_group)

        page.append(_section("DEVICE INFO"))

        info_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info_group.add_css_class("settings-group")
        info_group.set_margin_bottom(4)

        self._fw_label = Gtk.Label(label="—")
        self._fw_label.add_css_class("info-value")
        self._fw_label.set_xalign(1)
        info_group.append(_settings_row("Firmware", right_widget=self._fw_label))

        self._sn_label = Gtk.Label(label="—")
        self._sn_label.add_css_class("info-value")
        self._sn_label.set_xalign(1)
        info_group.append(_settings_row("Serial Number", right_widget=self._sn_label))

        addr_val = Gtk.Label(label=self._bt_device.address)
        addr_val.add_css_class("info-value")
        addr_val.set_xalign(1)
        info_group.append(_settings_row("Address", right_widget=addr_val))

        page.append(info_group)

        self._sync_anc_ui(ANCMode.OFF)
        self._sync_eq_ui("Balanced")

    def _update_conn_button(self):
        self._conn_btn.set_sensitive(True)
        if self._bt_device.connected:
            self._conn_btn.set_label("DISCONNECT")
            self._conn_btn.remove_css_class("connect-button")
            self._conn_btn.remove_css_class("connecting-button")
            self._conn_btn.add_css_class("disconnect-button")
        else:
            self._conn_btn.set_label("CONNECT")
            self._conn_btn.remove_css_class("disconnect-button")
            self._conn_btn.remove_css_class("connecting-button")
            self._conn_btn.add_css_class("connect-button")

    def _update_status_label(self):
        if self._bt_device.connected:
            self._conn_label.set_label("● Connected")
            self._conn_label.remove_css_class("status-disconnected")
            self._conn_label.add_css_class("status-connected")
        else:
            self._conn_label.set_label("○ Disconnected")
            self._conn_label.remove_css_class("status-connected")
            self._conn_label.add_css_class("status-disconnected")

    def cleanup(self):
        if self._nothing_dev:
            for h in self._nd_handlers:
                try:
                    self._nothing_dev.disconnect(h)
                except Exception:
                    pass
            self._nd_handlers = []
        self._bt.disconnect(self._bt_conn_handler)
        self._bt.disconnect(self._bt_disc_handler)

    def _connect_nothing(self, existing: NothingDevice | None):
        if existing is not None:
            self._nothing_dev = existing
        else:
            self._nothing_dev = NothingDevice(self._bt_device.address)
            if self._bt_device.connected:
                self._nothing_dev.connect_rfcomm()

        self._nd_handlers = [
            self._nothing_dev.connect("state-changed", self._on_state_changed),
            self._nothing_dev.connect("connected", self._on_rfcomm_connected),
            self._nothing_dev.connect("disconnected", self._on_rfcomm_disconnected),
        ]
        if self._nothing_dev.rfcomm_connected:
            self._on_state_changed(self._nothing_dev)
            GLib.timeout_add(800, self._query_volume)

    def _on_state_changed(self, dev: NothingDevice):
        state = dev.state
        self._visual.update(state.left_battery, state.right_battery, state.case_battery,
                            state.left_wearing, state.right_wearing)
        self._sync_anc_ui(state.anc_mode)
        self._sync_eq_ui(state.eq_preset)
        self._updating_ui = True
        if hasattr(self, "_in_ear_switch"):
            self._in_ear_switch.set_active(state.in_ear_detection)
        self._updating_ui = False
        if hasattr(self, "_fw_label"):
            self._fw_label.set_label(state.firmware_version or "—")
            self._sn_label.set_label(state.serial_number or "—")

    def _on_rfcomm_connected(self, _dev):
        print(f"[device page] RFCOMM connected to {self._bt_device.name}")
        GLib.timeout_add(800, self._query_volume)

    def _on_rfcomm_disconnected(self, _dev):
        print(f"[device page] RFCOMM disconnected from {self._bt_device.name}")

    def _query_volume(self):
        def _run():
            pct = _get_sink_volume(self._bt_device.address)
            if pct is not None:
                GLib.idle_add(self._apply_vol_display, pct)

        threading.Thread(target=_run, daemon=True).start()
        return False

    def _apply_vol_display(self, pct: int):
        if not hasattr(self, "_vol_scale") or self._vol_handler is None:
            return
        self._vol_scale.handler_block(self._vol_handler)
        self._vol_scale.set_value(pct)
        self._vol_label.set_label(f"{pct}%")
        self._vol_scale.handler_unblock(self._vol_handler)

    def _on_volume_changed(self, scale: Gtk.Scale):
        pct = int(scale.get_value())
        self._vol_label.set_label(f"{pct}%")
        if self._vol_debounce_id is not None:
            GLib.source_remove(self._vol_debounce_id)
        self._vol_debounce_id = GLib.timeout_add(150, self._do_set_volume, pct)

    def _do_set_volume(self, pct: int):
        self._vol_debounce_id = None
        threading.Thread(target=_set_sink_volume, args=(self._bt_device.address, pct), daemon=True).start()
        return False

    def _sync_anc_ui(self, active_mode: int):
        for mode, btn in self._anc_buttons:
            if mode == active_mode:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def _sync_eq_ui(self, active_preset: str):
        for preset, btn in self._eq_buttons:
            if preset == active_preset:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def _on_anc_clicked(self, _btn, mode: int):
        self._sync_anc_ui(mode)
        if self._nothing_dev:
            self._nothing_dev.set_anc_mode(mode)

    def _on_eq_clicked(self, _btn, preset: str):
        self._sync_eq_ui(preset)
        if self._nothing_dev:
            self._nothing_dev.set_eq_preset(preset)

    def _on_in_ear_toggled(self, switch: Gtk.Switch, state: bool):
        if self._updating_ui:
            return False
        if self._nothing_dev:
            self._nothing_dev.set_in_ear_detection(state)
        return False

    def _on_conn_btn_clicked(self, _btn):
        if self._bt_device.connected:
            self._bt.disconnect_device(self._bt_device.path)
        else:
            self._conn_btn.set_label("CONNECTING…")
            self._conn_btn.set_sensitive(False)
            self._conn_btn.remove_css_class("connect-button")
            self._conn_btn.add_css_class("connecting-button")
            self._bt.connect_device(self._bt_device.path, on_error=self._on_connect_failed)

    def _on_connect_failed(self):
        self._update_conn_button()

    def _on_bt_device_connected(self, _manager, path: str):
        if path != self._bt_device.path:
            return
        self._update_conn_button()
        self._update_status_label()
        if self._nothing_dev:
            from .. import profiles

            profiles.set_last_device(self._bt_device.address)
            self._nothing_dev.connect_rfcomm()

    def _on_bt_device_disconnected(self, _manager, path: str):
        if path != self._bt_device.path:
            return
        self._update_conn_button()
        self._update_status_label()
