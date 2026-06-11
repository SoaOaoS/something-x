<div align="center">

# Something X

**A Linux-native companion app for Nothing and CMF Bluetooth devices.**  
Built for [Omarchy](https://omarchy.org) · GTK4 · Pure black · JetBrains Mono · Nothing Red

[![PyPI](https://img.shields.io/pypi/v/something-x?color=red)](https://pypi.org/project/something-x/)
[![AUR](https://img.shields.io/aur/version/something-x?color=red)](https://aur.archlinux.org/packages/something-x)
[![License: MIT](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)](https://github.com/SoaOaoS/something-x)
[![CI](https://github.com/SoaOaoS/something-x/actions/workflows/ci.yml/badge.svg)](https://github.com/SoaOaoS/something-x/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-tracked-red)](https://github.com/SoaOaoS/something-x/actions/workflows/ci.yml)

</div>

---

## Features

| | Feature | Details |
|---|---|---|
| 🎧 | **Earbud visual** | Cairo-rendered glowing battery rings for L / R / Case, live updates |
| 🔇 | **ANC control** | Off · Noise Cancellation · Transparency over real RFCOMM protocol |
| 🎵 | **EQ presets** | Balanced · More Bass · More Treble · Voice |
| 🔊 | **Volume slider** | Direct PulseAudio / PipeWire A2DP sink control via `pactl` |
| 💾 | **Per-device profiles** | ANC + EQ saved per device address, restored automatically on reconnect |
| 🔋 | **Battery notifications** | Desktop alerts at 20 %, 15 %, 10 %, and 5 % per earbud and case |
| 🔗 | **Auto-connect RFCOMM** | Connects to the device protocol as soon as BlueZ reports it paired |
| 🏃 | **Background mode** | Closing the window keeps the app running; relaunch to reopen |
| 💻 | **CLI** | Control your earbuds from the terminal without opening the GUI |
| 📱 | **Device discovery** | BlueZ D-Bus scan with Nothing / CMF devices highlighted |
| ℹ️ | **Device info** | Firmware version and serial number read over RFCOMM |

---

## Device support

| Device | Battery | ANC | EQ | Volume | Firmware |
|---|:---:|:---:|:---:|:---:|:---:|
| Nothing Ear (1) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (2) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (a) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (stick) | ✅ | — | ✅ | ✅ | ✅ |
| CMF Buds / Buds Pro | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nothing Phone (1/2) | ✅ | — | — | — | — |
| Other Bluetooth devices | ✅* | — | — | ✅ | — |

<sub>* via BlueZ `Battery1` interface · RFCOMM features require an active connection</sub>

---

## Installation

### Arch / Omarchy (recommended)

Install system dependencies first:

```bash
sudo pacman -S python-gobject python-dbus python-cairo gtk4 libadwaita
```

Then install from **AUR**:

```bash
yay -S something-x
# or: paru -S something-x
```

Or via **pip**:

```bash
pip install something-x
```

### Other distros

<details>
<summary>Ubuntu 24.04+</summary>

```bash
sudo apt install python3-gi python3-dbus python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1
pip install something-x
```

</details>

<details>
<summary>Fedora 39+</summary>

```bash
sudo dnf install python3-gobject python3-dbus python3-cairo gtk4 libadwaita
pip install something-x
```

</details>

<details>
<summary>NixOS</summary>

```bash
nix run github:SoaOaoS/something-x
```

A `flake.nix` is included for reproducible builds.

</details>

### Run from source

```bash
git clone https://github.com/SoaOaoS/something-x
cd something-x
pip install -e .
something-x
```

---

## Usage

### GUI

```bash
something-x
```

1. **Splash** — animated intro, main window appears after ~2 s
2. **Home** — lists all paired Bluetooth devices; Nothing / CMF devices get a `NOTHING` badge
3. **Scan** — tap `SCAN FOR DEVICES` to run a 30 s BlueZ discovery
4. **Device page** — tap a card to open controls:
   - Battery rings (L / R / Case) update in real time
   - ANC and EQ apply immediately over RFCOMM and are saved to your profile
   - Volume slider drives the A2DP sink via `pactl`
   - Firmware version and serial number appear after RFCOMM connects
5. **Close** — hides to background; run `something-x` again to reopen

### CLI

Control your earbuds without opening the GUI:

```bash
# Battery levels
something-x --battery

# ANC mode
something-x --anc off
something-x --anc on
something-x --anc transparency

# EQ preset
something-x --eq balanced
something-x --eq bass
something-x --eq treble
something-x --eq voice

# Combine
something-x --anc on --eq bass

# Target a specific device by address
something-x --device AA:BB:CC:DD:EE:FF --battery
```

---

## Development releases

The `develop` branch publishes pre-release builds to PyPI automatically as `something-x-dev`:

```bash
pip install something-x-dev
something-x-dev
```

Dev builds use version numbers like `1.3.0.dev42`. Not for production use.

---

## Releases & versioning

Pushing to `main` triggers automatic versioning, a GitHub Release, a PyPI publish, and an AUR update — all from Conventional Commits:

| Commit prefix | Version bump |
|---|---|
| `feat!:` / `BREAKING CHANGE:` | Major `x.0.0` |
| `feat:` | Minor `1.x.0` |
| `fix:` / `perf:` / `refactor:` | Patch `1.0.x` |
| `docs:` / `chore:` / `style:` / `ci:` / `test:` | No release |

---

## Architecture

```
nothing_app/
├── application.py   Adw.Application — lifecycle, CSS, CLI arg handling, background mode
├── window.py        AdwNavigationView — home ↔ device routing, RFCOMM auto-connect manager
├── bluetooth.py     BlueZ D-Bus manager — device discovery, connect/disconnect signals
├── protocol.py      Nothing Ear 0x55 RFCOMM protocol (reverse-engineered from APK)
├── profiles.py      Per-device ANC/EQ persistence (~/.config/something-x/profiles.json)
├── splash.py        Animated splash screen (Cairo, typewriter, ripple rings)
├── data/
│   └── style.css    Glass-morphism CSS theme
└── pages/
    ├── home.py      Device list + scan button
    └── device.py    ANC / EQ / volume / settings + Cairo earbud visual
```

### Protocol

Frame format: `[SOF=0x55][ctrl:2 LE][cmd:2 LE][len:2 LE][FSN:1][payload][CRC16:2 LE]`

All outgoing frames use `ctrl=0x0160` with CRC16-ARC. The device silently drops SET commands if any frame in the session was sent without CRC.

Enable raw frame logging:

```bash
SOMETHING_X_DEBUG=1 something-x
```

---

## Contributing

The RFCOMM protocol in [`nothing_app/protocol.py`](nothing_app/protocol.py) is reverse-engineered from the official Android APK. If your device uses different command IDs, channels, or ANC values, patches are very welcome — please include the raw RFCOMM dump (`SOMETHING_X_DEBUG=1`) in your issue or PR.

---

## License

[MIT](LICENSE)
