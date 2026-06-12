import base64
import json
import os
from dataclasses import asdict, dataclass

_DIR = os.path.expanduser("~/.config/something-x")
_THEME_FILE = os.path.join(_DIR, "theme.json")

ACCENT_PRESETS: list[tuple[str, str]] = [
    ("#e83535", "Red"),
    ("#3b82f6", "Blue"),
    ("#10b981", "Emerald"),
    ("#f59e0b", "Amber"),
    ("#8b5cf6", "Violet"),
    ("#ec4899", "Pink"),
    ("#06b6d4", "Cyan"),
    ("#f97316", "Orange"),
]

BG_PRESETS: list[tuple[str, str]] = [
    ("#000000", "Black"),
    ("#0d1117", "Abyss"),
    ("#1a1b26", "Night"),
    ("#0f0e17", "Ink"),
    ("#1e1e2e", "Mocha"),
    ("#0a0f1e", "Ocean"),
    ("#120028", "Void"),
    ("#0a1a0a", "Forest"),
]

TEXTURES: list[tuple[str, str]] = [
    ("none",      "None"),
    ("dots",      "Dots"),
    ("scanlines", "Lines"),
    ("noise",     "Noise"),
]

FONT_PRESETS: list[tuple[str, str]] = [
    ("",                        "System"),
    ("Adwaita Sans",            "Adwaita"),
    ("iA Writer Quattro S",     "iA Writer"),
    ("JetBrainsMono Nerd Font", "Mono"),
]


@dataclass
class Theme:
    accent: str = "#e83535"
    bg_color: str = "#000000"
    window_opacity: float = 1.0
    card_opacity: float = 1.0
    blur: int = 0
    texture: str = "none"
    font_family: str = ""


def load() -> Theme:
    try:
        with open(_THEME_FILE) as f:
            data = json.load(f)
        # migrate old card_blur key
        if "card_blur" in data and "blur" not in data:
            data["blur"] = data.pop("card_blur")
        valid = {k: v for k, v in data.items() if k in Theme.__dataclass_fields__}
        return Theme(**valid)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return Theme()


def save(t: Theme) -> None:
    os.makedirs(_DIR, exist_ok=True)
    with open(_THEME_FILE, "w") as f:
        json.dump(asdict(t), f, indent=2)


# ── Color helpers ─────────────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(h: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(h)
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def _darken(h: str, factor: float) -> str:
    r, g, b = hex_to_rgb(h)
    return f"#{min(255,int(r*factor)):02x}{min(255,int(g*factor)):02x}{min(255,int(b*factor)):02x}"


def _lighten(h: str, factor: float) -> str:
    r, g, b = hex_to_rgb(h)
    return (
        f"#{min(255,int(r+(255-r)*factor)):02x}"
        f"{min(255,int(g+(255-g)*factor)):02x}"
        f"{min(255,int(b+(255-b)*factor)):02x}"
    )


# ── Texture patterns ──────────────────────────────────────────────────────────

def _texture_css(name: str) -> str:
    if name == "dots":
        return (
            "background-image:"
            " radial-gradient(circle, rgba(255,255,255,0.06) 1px, transparent 1px);"
            " background-size: 20px 20px;"
        )
    if name == "scanlines":
        return (
            "background-image:"
            " repeating-linear-gradient("
            "to bottom, rgba(255,255,255,0.028) 0px, rgba(255,255,255,0.028) 1px,"
            " transparent 1px, transparent 4px);"
        )
    if name == "noise":
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
            '<filter id="n">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.72" numOctaves="4" stitchTiles="stitch"/>'
            '<feColorMatrix type="saturate" values="0"/>'
            '</filter>'
            '<rect width="128" height="128" filter="url(#n)" opacity="0.07"/>'
            '</svg>'
        )
        enc = base64.b64encode(svg.encode()).decode()
        return (
            f'background-image: url("data:image/svg+xml;base64,{enc}");'
            ' background-size: 128px 128px;'
        )
    return "background-image: none;"


# ── CSS generation ────────────────────────────────────────────────────────────

def generate_css(t: Theme) -> str:
    acc = t.accent
    dark    = _darken(acc, 0.72)
    darker  = _darken(acc, 0.62)
    darkest = _darken(acc, 0.52)
    hover   = _lighten(acc, 0.07)

    def a(alpha: float) -> str:
        return _rgba(acc, alpha)

    co = max(0.15, min(1.0, t.card_opacity))
    bg = t.bg_color
    # subtle gradient variants derived from bg_color
    bg_light = _lighten(bg, 0.05)
    bg_dark  = _darken(bg, 0.80) if bg != "#000000" else bg

    c1  = co * 0.055;  c2  = co * 0.022
    h1  = co * 0.082;  h2  = co * 0.036
    s1  = co * 0.048;  s2  = co * 0.018
    a1  = co * 0.040;  a2  = co * 0.014

    # blur and texture live on .app-background (behind content) — not on content widgets
    blur_rule = f"filter: blur({t.blur}px);" if t.blur else ""
    texture = _texture_css(t.texture)

    font_rule = f'* {{ font-family: "{t.font_family}"; }}' if t.font_family else ""

    return f"""/* Nothing X — generated theme override */

{font_rule}
@define-color accent_color {acc};
@define-color accent_bg_color {acc};
@define-color accent_fg_color #ffffff;

@keyframes dot-pulse {{
    0%, 100% {{ box-shadow: 0 0 6px {a(0.62)}; }}
    50%       {{ box-shadow: 0 0 14px {a(0.92)}, 0 0 28px {a(0.20)}; }}
}}
@keyframes scan-bloom {{
    0%, 100% {{
        box-shadow:
            0 0 0 1px {a(0.12)},
            0 4px 24px {a(0.38)},
            0 12px 48px {a(0.15)},
            inset 0 1px 0 rgba(255,148,148,0.24),
            inset 0 -1px 0 rgba(0,0,0,0.38);
    }}
    50% {{
        box-shadow:
            0 0 0 1px {a(0.22)},
            0 4px 34px {a(0.54)},
            0 12px 68px {a(0.24)},
            inset 0 1px 0 rgba(255,148,148,0.30),
            inset 0 -1px 0 rgba(0,0,0,0.38);
    }}
}}

window, .background {{ background-color: {bg}; }}

/* Background layer — gradient, texture, blur all here.
   Content (nav view) sits above as a sibling, so blur doesn't touch it. */
.app-background {{
    background: linear-gradient(180deg, {bg_light} 0%, {bg_dark} 18%);
    {blur_rule}
    {texture}
}}

/* Make the navigation stack and scroll containers transparent
   so the background layer shows through cleanly. */
adw-navigation-view, adw-toolbar-view {{ background-color: transparent; }}
scrolledwindow, viewport {{ background-color: transparent; }}
.nothing-page {{ background: transparent; }}

.device-card {{
    background: linear-gradient(155deg, rgba(255,255,255,{c1:.4f}) 0%, rgba(255,255,255,{c2:.4f}) 100%);
}}
.device-card:hover {{
    background: linear-gradient(155deg, rgba(255,255,255,{h1:.4f}) 0%, rgba(255,255,255,{h2:.4f}) 100%);
}}
.settings-group {{
    background: linear-gradient(180deg, rgba(255,255,255,{s1:.4f}) 0%, rgba(255,255,255,{s2:.4f}) 100%);
}}
.anc-container {{
    background: linear-gradient(180deg, rgba(255,255,255,{a1:.4f}) 0%, rgba(255,255,255,{a2:.4f}) 100%);
}}

.anc-button.active, .anc-button:checked {{
    background: linear-gradient(160deg, {acc} 0%, {dark} 100%);
    box-shadow: 0 2px 16px {a(0.38)}, inset 0 1px 0 rgba(255,255,255,0.20);
}}
.anc-button.active:hover, .anc-button:checked:hover {{
    background: linear-gradient(160deg, {hover} 0%, {darker} 100%);
}}
.eq-button.active, .eq-button:checked {{
    background: linear-gradient(160deg, {acc} 0%, {dark} 100%);
    border-color: transparent;
    box-shadow: 0 2px 16px {a(0.36)}, inset 0 1px 0 rgba(255,255,255,0.20);
}}
.eq-button.active:hover, .eq-button:checked:hover {{
    background: linear-gradient(160deg, {hover} 0%, {darker} 100%);
}}

scale trough highlight {{
    background: linear-gradient(90deg, {darkest} 0%, {acc} 65%, {hover} 100%);
    box-shadow: 0 0 10px {a(0.36)};
}}
scale slider:active {{
    box-shadow:
        0 0 0 5px {a(0.15)},
        0 0 0 10px {a(0.06)},
        0 2px 12px rgba(0,0,0,0.65),
        inset 0 1px 0 rgba(255,255,255,0.50);
}}

switch:checked {{
    background: linear-gradient(160deg, {acc} 0%, {dark} 100%);
    border-color: {a(0.18)};
    box-shadow: 0 0 14px {a(0.32)}, 0 0 36px {a(0.10)}, inset 0 2px 6px rgba(0,0,0,0.20);
}}

.scan-button {{
    background: linear-gradient(160deg, {acc} 0%, {dark} 100%);
    border-color: {a(0.18)};
    box-shadow:
        0 0 0 1px {a(0.12)},
        0 4px 24px {a(0.38)},
        0 12px 48px {a(0.15)},
        inset 0 1px 0 rgba(255,148,148,0.24),
        inset 0 -1px 0 rgba(0,0,0,0.38);
}}
.scan-button:hover {{
    background: linear-gradient(160deg, {hover} 0%, {darker} 100%);
    box-shadow:
        0 0 0 1px {a(0.20)},
        0 6px 32px {a(0.52)},
        0 16px 60px {a(0.22)},
        inset 0 1px 0 rgba(255,148,148,0.30),
        inset 0 -1px 0 rgba(0,0,0,0.38);
}}
.scan-button:active {{
    background: linear-gradient(160deg, {dark} 0%, {darkest} 100%);
    box-shadow:
        0 0 0 1px {a(0.08)},
        0 2px 12px {a(0.28)},
        inset 0 1px 0 rgba(255,148,148,0.16),
        inset 0 -1px 0 rgba(0,0,0,0.42);
}}

.disconnect-button {{
    background: {a(0.07)};
    border-color: {a(0.18)};
}}
.disconnect-button label {{ color: {a(0.75)}; }}
.disconnect-button:hover {{
    background: {a(0.12)};
    border-color: {a(0.30)};
    box-shadow: 0 0 16px {a(0.11)}, inset 0 1px 0 rgba(255,255,255,0.04);
}}
.disconnect-button:hover label {{ color: {acc}; }}

.nothing-dot {{
    background-color: {acc};
    box-shadow: 0 0 6px {a(0.62)};
}}
.status-nothing {{
    color: {acc};
    background: {a(0.10)};
    border-color: {a(0.22)};
}}
progressbar progress {{ background-color: {acc}; }}
"""
