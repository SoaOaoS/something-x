import math
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from ..theme import ACCENT_PRESETS, BG_PRESETS, TEXTURES, Theme, hex_to_rgb


# ── Swatch drawing area ───────────────────────────────────────────────────────

class _Swatch(Gtk.DrawingArea):
    def __init__(self, color: str, on_picked: Callable[[str], None]):
        super().__init__()
        self._color = color
        self._active = False
        self._hovered = False
        self.set_size_request(40, 40)
        self.set_draw_func(self._draw)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: on_picked(color))
        self.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self._set_hover(True))
        motion.connect("leave", lambda *_: self._set_hover(False))
        self.add_controller(motion)

    def set_active(self, active: bool):
        self._active = active
        self.queue_draw()

    def _set_hover(self, h: bool):
        self._hovered = h
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        r, g, b = hex_to_rgb(self._color)
        cx, cy = w / 2, h / 2
        outer = min(w, h) / 2 - 2
        inner = outer - 3

        if self._active:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.arc(cx, cy, outer, 0, 2 * math.pi)
            cr.fill()

        rf, gf, bf = r / 255, g / 255, b / 255
        alpha = 0.80 if self._hovered else 1.0
        cr.set_source_rgba(rf, gf, bf, alpha)
        cr.arc(cx, cy, inner if self._active else outer - 1, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgba(0, 0, 0, 0.20)
        cr.set_line_width(1)
        cr.arc(cx, cy, inner if self._active else outer - 1, 0, 2 * math.pi)
        cr.stroke()


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _make_slider(
    min_val: float, max_val: float, step: float, value: float
) -> tuple[Gtk.Scale, Gtk.Label]:
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_val, max_val, step)
    scale.set_hexpand(True)
    scale.set_draw_value(False)
    scale.add_css_class("volume-slider")
    scale.set_value(value)
    lbl = Gtk.Label()
    lbl.add_css_class("volume-label")
    lbl.set_width_chars(5)
    lbl.set_xalign(1)
    return scale, lbl


def _swatch_row(presets: list[tuple[str, str]], current: str, on_picked: Callable[[str], None]) -> tuple[Gtk.Box, list[_Swatch]]:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.set_margin_top(16)
    box.set_margin_bottom(16)
    box.set_margin_start(18)
    box.set_margin_end(18)
    box.set_halign(Gtk.Align.CENTER)
    box.set_hexpand(True)
    swatches: list[_Swatch] = []
    for color, label in presets:
        sw = _Swatch(color, on_picked)
        sw.set_tooltip_text(label)
        sw.set_active(color.lower() == current.lower())
        box.append(sw)
        swatches.append(sw)
    return box, swatches


# ── ThemePage ─────────────────────────────────────────────────────────────────

class ThemePage(Gtk.Box):
    def __init__(self, theme: Theme, on_change: Callable[[Theme], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        import dataclasses
        self._theme = dataclasses.replace(theme)
        self._on_change_cb = on_change

        self._accent_swatches: list[_Swatch] = []
        self._accent_color_btn: Gtk.ColorButton | None = None
        self._accent_color_handler: int | None = None

        self._bg_swatches: list[_Swatch] = []
        self._bg_color_btn: Gtk.ColorButton | None = None
        self._bg_color_handler: int | None = None

        self._opacity_scale: Gtk.Scale | None = None
        self._opacity_handler: int | None = None
        self._card_scale: Gtk.Scale | None = None
        self._card_handler: int | None = None
        self._blur_scale: Gtk.Scale | None = None
        self._blur_handler: int | None = None
        self._texture_btns: list[tuple[str, Gtk.ToggleButton]] = []
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.add_css_class("nothing-page")
        scroll.set_child(page)
        self.append(scroll)

        self._build_accent(page)
        self._build_bg_color(page)
        self._build_glass(page)
        self._build_blur(page)
        self._build_texture(page)
        self._build_reset(page)

    def _build_accent(self, page: Gtk.Box):
        page.append(_section("ACCENT COLOR"))

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class("settings-group")
        group.set_margin_bottom(4)

        swatch_box, self._accent_swatches = _swatch_row(
            ACCENT_PRESETS, self._theme.accent, self._on_accent_swatch
        )
        group.append(swatch_box)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_opacity(0.3)
        group.append(sep)

        rgba = Gdk.RGBA()
        rgba.parse(self._theme.accent)
        self._accent_color_btn = Gtk.ColorButton(rgba=rgba)
        self._accent_color_btn.set_valign(Gtk.Align.CENTER)
        self._accent_color_btn.set_use_alpha(False)
        self._accent_color_handler = self._accent_color_btn.connect("color-set", self._on_accent_color_set)
        group.append(_settings_row("Custom color", "Pick any accent", self._accent_color_btn))

        page.append(group)

    def _build_bg_color(self, page: Gtk.Box):
        page.append(_section("BACKGROUND COLOR"))

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class("settings-group")
        group.set_margin_bottom(4)

        swatch_box, self._bg_swatches = _swatch_row(
            BG_PRESETS, self._theme.bg_color, self._on_bg_swatch
        )
        group.append(swatch_box)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_opacity(0.3)
        group.append(sep)

        rgba = Gdk.RGBA()
        rgba.parse(self._theme.bg_color)
        self._bg_color_btn = Gtk.ColorButton(rgba=rgba)
        self._bg_color_btn.set_valign(Gtk.Align.CENTER)
        self._bg_color_btn.set_use_alpha(False)
        self._bg_color_handler = self._bg_color_btn.connect("color-set", self._on_bg_color_set)
        group.append(_settings_row("Custom background", "Pick any dark color", self._bg_color_btn))

        page.append(group)

    def _build_glass(self, page: Gtk.Box):
        page.append(_section("TRANSPARENCY"))

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class("settings-group")
        group.set_margin_bottom(4)

        self._opacity_scale, op_lbl = _make_slider(0.05, 1.0, 0.05, self._theme.window_opacity)
        op_lbl.set_label(f"{int(self._theme.window_opacity * 100)}%")
        self._opacity_handler = self._opacity_scale.connect(
            "value-changed", self._on_opacity_changed, op_lbl
        )
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row_box.set_hexpand(True)
        row_box.append(self._opacity_scale)
        row_box.append(op_lbl)
        group.append(_settings_row("Window opacity", "How transparent the whole window is", row_box))

        self._card_scale, card_lbl = _make_slider(0.15, 1.0, 0.05, self._theme.card_opacity)
        card_lbl.set_label(f"{int(self._theme.card_opacity * 100)}%")
        self._card_handler = self._card_scale.connect(
            "value-changed", self._on_card_changed, card_lbl
        )
        card_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_row.set_hexpand(True)
        card_row.append(self._card_scale)
        card_row.append(card_lbl)
        group.append(_settings_row("Card opacity", "Surface and panel transparency", card_row))

        page.append(group)

    def _build_blur(self, page: Gtk.Box):
        page.append(_section("BACKGROUND BLUR"))

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class("settings-group")
        group.set_margin_bottom(4)

        self._blur_scale, blur_lbl = _make_slider(0, 20, 1, self._theme.blur)
        blur_lbl.set_label(f"{self._theme.blur}px")
        self._blur_handler = self._blur_scale.connect(
            "value-changed", self._on_blur_changed, blur_lbl
        )
        blur_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        blur_row.set_hexpand(True)
        blur_row.append(self._blur_scale)
        blur_row.append(blur_lbl)
        group.append(_settings_row("Blur amount", "Blurs the page background", blur_row))

        page.append(group)

    def _build_texture(self, page: Gtk.Box):
        page.append(_section("TEXTURE"))

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        group.add_css_class("settings-group")
        group.set_margin_bottom(4)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        btn_box.add_css_class("linked")
        btn_box.set_margin_top(14)
        btn_box.set_margin_bottom(14)
        btn_box.set_margin_start(18)
        btn_box.set_margin_end(18)
        btn_box.set_hexpand(True)

        for key, label in TEXTURES:
            btn = Gtk.ToggleButton(label=label)
            btn.set_hexpand(True)
            btn.set_active(key == self._theme.texture)
            btn.connect("toggled", self._on_texture_toggled, key)
            btn_box.append(btn)
            self._texture_btns.append((key, btn))

        group.append(btn_box)
        page.append(group)

    def _build_reset(self, page: Gtk.Box):
        reset = Gtk.Button(label="RESET TO DEFAULT")
        reset.add_css_class("disconnect-button")
        reset.set_margin_top(32)
        reset.set_margin_bottom(8)
        reset.set_halign(Gtk.Align.CENTER)
        reset.connect("clicked", self._on_reset)
        page.append(reset)

    # ── Handlers — accent ─────────────────────────────────────────────────────

    def _on_accent_swatch(self, color: str):
        self._theme.accent = color
        self._update_accent_swatches()
        if self._accent_color_btn and self._accent_color_handler:
            rgba = Gdk.RGBA()
            rgba.parse(color)
            self._accent_color_btn.handler_block(self._accent_color_handler)
            self._accent_color_btn.set_rgba(rgba)
            self._accent_color_btn.handler_unblock(self._accent_color_handler)
        self._emit()

    def _on_accent_color_set(self, btn: Gtk.ColorButton):
        rgba = btn.get_rgba()
        self._theme.accent = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255),
        )
        self._update_accent_swatches()
        self._emit()

    # ── Handlers — background color ───────────────────────────────────────────

    def _on_bg_swatch(self, color: str):
        self._theme.bg_color = color
        self._update_bg_swatches()
        if self._bg_color_btn and self._bg_color_handler:
            rgba = Gdk.RGBA()
            rgba.parse(color)
            self._bg_color_btn.handler_block(self._bg_color_handler)
            self._bg_color_btn.set_rgba(rgba)
            self._bg_color_btn.handler_unblock(self._bg_color_handler)
        self._emit()

    def _on_bg_color_set(self, btn: Gtk.ColorButton):
        rgba = btn.get_rgba()
        self._theme.bg_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255),
        )
        self._update_bg_swatches()
        self._emit()

    # ── Handlers — sliders ────────────────────────────────────────────────────

    def _on_opacity_changed(self, scale: Gtk.Scale, lbl: Gtk.Label):
        val = round(scale.get_value() / 0.05) * 0.05
        self._theme.window_opacity = val
        lbl.set_label(f"{int(val * 100)}%")
        self._emit()

    def _on_card_changed(self, scale: Gtk.Scale, lbl: Gtk.Label):
        val = round(scale.get_value() / 0.05) * 0.05
        self._theme.card_opacity = val
        lbl.set_label(f"{int(val * 100)}%")
        self._emit()

    def _on_blur_changed(self, scale: Gtk.Scale, lbl: Gtk.Label):
        val = int(scale.get_value())
        self._theme.blur = val
        lbl.set_label(f"{val}px")
        self._emit()

    def _on_texture_toggled(self, btn: Gtk.ToggleButton, key: str):
        if not btn.get_active():
            return
        for k, b in self._texture_btns:
            if k != key:
                b.handler_block_by_func(self._on_texture_toggled)
                b.set_active(False)
                b.handler_unblock_by_func(self._on_texture_toggled)
        self._theme.texture = key
        self._emit()

    def _on_reset(self, _btn):
        import dataclasses
        self._theme = Theme()
        self._reload_controls()
        self._emit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_accent_swatches(self):
        for sw, (color, _) in zip(self._accent_swatches, ACCENT_PRESETS):
            sw.set_active(color.lower() == self._theme.accent.lower())

    def _update_bg_swatches(self):
        for sw, (color, _) in zip(self._bg_swatches, BG_PRESETS):
            sw.set_active(color.lower() == self._theme.bg_color.lower())

    def _reload_controls(self):
        if self._opacity_scale and self._opacity_handler:
            self._opacity_scale.handler_block(self._opacity_handler)
            self._opacity_scale.set_value(self._theme.window_opacity)
            self._opacity_scale.handler_unblock(self._opacity_handler)

        if self._card_scale and self._card_handler:
            self._card_scale.handler_block(self._card_handler)
            self._card_scale.set_value(self._theme.card_opacity)
            self._card_scale.handler_unblock(self._card_handler)

        if self._blur_scale and self._blur_handler:
            self._blur_scale.handler_block(self._blur_handler)
            self._blur_scale.set_value(self._theme.blur)
            self._blur_scale.handler_unblock(self._blur_handler)

        self._update_accent_swatches()
        self._update_bg_swatches()

        if self._accent_color_btn and self._accent_color_handler:
            rgba = Gdk.RGBA()
            rgba.parse(self._theme.accent)
            self._accent_color_btn.handler_block(self._accent_color_handler)
            self._accent_color_btn.set_rgba(rgba)
            self._accent_color_btn.handler_unblock(self._accent_color_handler)

        if self._bg_color_btn and self._bg_color_handler:
            rgba = Gdk.RGBA()
            rgba.parse(self._theme.bg_color)
            self._bg_color_btn.handler_block(self._bg_color_handler)
            self._bg_color_btn.set_rgba(rgba)
            self._bg_color_btn.handler_unblock(self._bg_color_handler)

        for key, btn in self._texture_btns:
            btn.handler_block_by_func(self._on_texture_toggled)
            btn.set_active(key == self._theme.texture)
            btn.handler_unblock_by_func(self._on_texture_toggled)

    def _emit(self):
        import dataclasses
        self._on_change_cb(dataclasses.replace(self._theme))
