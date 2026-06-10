import math
import time
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib


_DURATION_MS = 2300


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    p = -2 * t + 2
    return 1 - p * p * p / 2


def _p(t: float, start: float, end: float) -> float:
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    return (t - start) / (end - start)


class SplashScreen(Adw.Window):
    def __init__(self, on_done):
        super().__init__()
        self._on_done = on_done
        self._start: float | None = None
        self._done = False

        self.set_default_size(420, 780)
        self.set_resizable(False)
        self.set_decorated(False)
        self.add_css_class("splash-window")

        area = Gtk.DrawingArea()
        area.set_draw_func(self._draw)
        area.set_hexpand(True)
        area.set_vexpand(True)
        self.set_content(area)
        self._area = area

    def start(self):
        self._start = time.monotonic()
        GLib.timeout_add(16, self._frame)

    def _frame(self) -> bool:
        if self._done:
            return False
        elapsed = (time.monotonic() - self._start) * 1000
        self._area.queue_draw()
        if elapsed >= _DURATION_MS + 80:
            self._done = True
            GLib.idle_add(self._on_done)
            return False
        return True

    def _draw(self, _area, cr, width, height):
        if self._start is None:
            cr.set_source_rgb(0, 0, 0)
            cr.paint()
            return

        t = (time.monotonic() - self._start) * 1000
        cx, cy = width / 2, height / 2

        cr.set_source_rgb(0, 0, 0)
        cr.paint()

        # global fade out 1750 → 2300ms
        fade = 1.0 - _ease_in_out(_p(t, 1750, 2300))
        if fade < 0.004:
            return

        dot_cy = cy - 62
        title_y = cy + 4
        sub_y = cy + 38

        # ── red dot ──────────────────────────────────────────────────────────
        dot_in = _ease_out(_p(t, 0, 380))
        if dot_in > 0:
            pulse = 1.0 + math.sin(t / 380 * math.pi * 2) * 0.18
            glow_r = 22 * pulse
            rg = cairo.RadialGradient(cx, dot_cy, 0, cx, dot_cy, glow_r)
            rg.add_color_stop_rgba(0, 0.91, 0.21, 0.21, 0.32 * dot_in * fade)
            rg.add_color_stop_rgba(1, 0.91, 0.21, 0.21, 0)
            cr.set_source(rg)
            cr.arc(cx, dot_cy, glow_r, 0, 2 * math.pi)
            cr.fill()

            cr.set_source_rgba(0.91, 0.21, 0.21, dot_in * fade)
            cr.arc(cx, dot_cy, 4.5 * dot_in, 0, 2 * math.pi)
            cr.fill()

        # ── ripple rings ─────────────────────────────────────────────────────
        for i, delay in enumerate((0, 190, 380)):
            rp = _p(t, 80 + delay, 900 + delay)
            if 0 < rp < 1:
                r = 5 + _ease_out(rp) * 85
                alpha = ((1 - rp) ** 1.4) * (0.55 - i * 0.12) * fade
                cr.set_source_rgba(0.91, 0.21, 0.21, alpha)
                cr.set_line_width(1.0 + (1 - rp) * 0.6)
                cr.arc(cx, dot_cy, r, 0, 2 * math.pi)
                cr.stroke()

        # ── "SOMETHING X" typewriter ─────────────────────────────────────────
        title = "SOMETHING X"
        n_visible = min(int(_p(t, 450, 1020) * (len(title) + 1)), len(title))

        cr.select_font_face("JetBrains Mono", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(32)

        # stable centering from full string measurement
        full_te = cr.text_extents(title)
        px = cx - full_te.width / 2 - full_te.x_bearing

        for i, ch in enumerate(title[:n_visible]):
            is_x = ch == "X" and i == len(title) - 1
            r, g, b = (0.91, 0.21, 0.21) if is_x else (1.0, 1.0, 1.0)
            cr.set_source_rgba(r, g, b, fade)
            te = cr.text_extents(ch)
            cr.move_to(px - te.x_bearing, title_y)
            cr.show_text(ch)
            px += te.x_advance

        # cursor: blinks after typing (400ms cycle), gone after 1600ms
        cursor_visible = n_visible < len(title) or (
            t < 1600 and int((_p(t, 1020, 1600) * 1000) / 420) % 2 == 0
        )
        if cursor_visible:
            cr.set_source_rgba(0.91, 0.21, 0.21, 0.85 * fade)
            cr.rectangle(px + 3, title_y - 27, 2, 31)
            cr.fill()

        # ── "FOR LINUX" with letter-spacing ──────────────────────────────────
        sub_p = _ease_out(_p(t, 880, 1200)) * fade
        if sub_p > 0.004:
            cr.select_font_face("JetBrains Mono", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
            cr.set_font_size(11)
            sub = "FOR LINUX"
            spacing = 5.5
            advances = [cr.text_extents(ch).x_advance for ch in sub]
            total_w = sum(advances) + spacing * (len(sub) - 1)
            lx = cx - total_w / 2
            for ch, adv in zip(sub, advances, strict=True):
                te = cr.text_extents(ch)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.32 * sub_p)
                cr.move_to(lx - te.x_bearing, sub_y)
                cr.show_text(ch)
                lx += adv + spacing

        # ── thin horizontal rule under subtitle ──────────────────────────────
        rule_p = _ease_out(_p(t, 1050, 1350)) * fade
        if rule_p > 0.004:
            rule_y = sub_y + 18
            rule_half = 28 * rule_p
            cr.set_source_rgba(0.91, 0.21, 0.21, 0.22 * rule_p)
            cr.set_line_width(1)
            cr.move_to(cx - rule_half, rule_y)
            cr.line_to(cx + rule_half, rule_y)
            cr.stroke()

        # ── bottom caption ────────────────────────────────────────────────────
        cap_p = _ease_out(_p(t, 1150, 1500)) * fade
        if cap_p > 0.004:
            cr.select_font_face("JetBrains Mono", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
            cr.set_font_size(8)
            cap = "OPEN SOURCE  ·  MADE FOR OMARCHY"
            te = cr.text_extents(cap)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.09 * cap_p)
            cr.move_to(cx - te.width / 2 - te.x_bearing, height - 52)
            cr.show_text(cap)
