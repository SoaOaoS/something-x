# Something X — for Linux

> A Linux-native companion app for **Nothing** and **CMF** Bluetooth devices.  
> Built for [Omarchy](https://omarchy.org) (Hyprland / Wayland) — pure black, JetBrains Mono, Nothing Red.

```
  ●  SOMETHING X
     FOR LINUX
```

[![PyPI](https://img.shields.io/pypi/v/something-x)](https://pypi.org/project/something-x/)
[![License: MIT](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-blue)](https://github.com/SoaOaoS/something-x)

---

## Features

- **Animated splash screen** — Nothing-branded intro with typewriter effect and ripple rings
- **Earbud visual** — Cairo-rendered glowing battery rings with radial gradients for L / R / Case
- **ANC control** — Off · Noise Cancellation · Transparency (real RFCOMM protocol)
- **EQ presets** — Balanced · More Bass · More Treble · Voice
- **Volume slider** — controls the PulseAudio/PipeWire A2DP sink directly
- **Firmware version & serial number** — read from the device over RFCOMM
- **In-ear detection toggle**
- **Device discovery** — BlueZ D-Bus; Nothing/CMF devices highlighted with a badge
- **Scan for new devices** — 30 s BlueZ discovery window
- **Glass morphism UI** — pure black base, frosted glass cards, red gradient accents

---

## Device support

| Device | Discovery | Battery | ANC | EQ | Volume | Firmware |
|---|---|---|---|---|---|---|
| Nothing Ear (1) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (2) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (a) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (stick) | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| CMF Buds / Buds Pro | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Phone (1/2) | ✅ | — | — | — | — | — |
| Other BT devices | ✅ | ✅* | — | — | ✅ | — |

\* via BlueZ `Battery1` interface · RFCOMM features require the device to be connected

---

## Requirements

### System packages (Arch / Omarchy)

```bash
sudo pacman -S python-gobject python-dbus python-cairo gtk4 libadwaita
```

| Package | Purpose |
|---|---|
| `python-gobject` | GTK4, libadwaita, GLib bindings |
| `python-dbus` | BlueZ D-Bus access |
| `python-cairo` | Cairo drawing (earbud visual, splash) |
| `gtk4` | UI toolkit |
| `libadwaita` | Navigation, dark theme |

> `pactl` (from `libpulse` / `pipewire-pulse`) is used for volume control — already present on any PulseAudio/PipeWire system.

---

## Installation

### Recommended — pip (after system packages above)

```bash
pip install something-x
something-x
```

### Run from source

```bash
git clone https://github.com/SoaOaoS/something-x
cd something-x
./somethingx
```

### Desktop launcher (Walker / Rofi / app menu)

```bash
cp nothing_app/data/com.something.x.omarchy.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

---

## Usage

```
./somethingx        # from source
something-x         # if installed via pip
```

1. **Splash** — animated intro, main window opens after ~2.3 s
2. **Home** — all paired BT devices; Nothing/CMF get a `NOTHING` badge
3. **Scan** — "SCAN FOR DEVICES" runs 30 s BlueZ discovery
4. **Device page** — tap a card to open controls:
   - Battery rings (L / R / Case) update in real time
   - ANC and EQ apply immediately over RFCOMM
   - Volume slider controls the A2DP sink via `pactl`
   - Firmware and serial number shown after connection
5. **Disconnect** — red button sends a clean BlueZ disconnect

---

## Releases & versioning

This project uses **Conventional Commits**. Pushing to `main` triggers automatic versioning and a PyPI release:

| Commit prefix | Version bump | Example |
|---|---|---|
| `feat!:` / `BREAKING CHANGE` | Major (`x.0.0`) | `feat!: new protocol engine` |
| `feat:` | Minor (`1.x.0`) | `feat: add Ear (open) support` |
| `fix:` / `perf:` / `refactor:` | Patch (`1.0.x`) | `fix: ANC off not applying` |
| `docs:` / `chore:` / `style:` / `ci:` | — (no release) | `chore: update readme` |

---

## Architecture

```
nothing_app/
├── application.py      Adw.Application — CSS, dark theme, splash handoff
├── splash.py           Animated splash screen (Cairo, typewriter, ripples)
├── window.py           AdwNavigationView — home ↔ device routing
├── bluetooth.py        BlueZ D-Bus manager (discovery, connect/disconnect signals)
├── protocol.py         Nothing Ear RFCOMM 0x55 binary protocol (reverse-engineered)
├── data/
│   └── style.css       Nothing X glass-morphism CSS theme
└── pages/
    ├── home.py         Device list + scan button
    └── device.py       ANC / EQ / volume / settings + Cairo earbud visual
```

### Protocol notes

Frame format: `[SOF=0x55][ctrl:2 LE][cmd:2 LE][len:2 LE][FSN:1][payload][crc16:2 LE]`

All outgoing frames use `ctrl=0x0160` with CRC16-ARC — the device silently drops SET commands if any frame in the session was sent without CRC.

---

## Contributing

The RFCOMM protocol in [nothing_app/protocol.py](nothing_app/protocol.py) is reverse-engineered from the official Android APK. If your device uses different command IDs or channel numbers, patches are very welcome.

---

## License

MIT
