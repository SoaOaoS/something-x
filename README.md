# Something X — for Omarchy

A Linux-native companion app for **Nothing** and **CMF** Bluetooth devices, built to match the Nothing X aesthetic on [Omarchy](https://omarchy.org) (Hyprland / Wayland).

```
 ● SOMETHING X
 ──────────────────────────────
  MY DEVICES

  ┌──────────────────────────────┐
  │  🎧  Nothing Ear (2)  NOTHING│
  │  ● Connected          82%   │
  └──────────────────────────────┘

  OTHER DEVICES

  ┌──────────────────────────────┐
  │  📱  OnePlus 12              │
  │  ○ Disconnected              │
  └──────────────────────────────┘
```

---

## Features

- **Device discovery** — lists all paired Bluetooth devices via BlueZ D-Bus; Nothing/CMF devices are highlighted
- **Earbud visual** — Cairo-rendered battery rings (green / yellow / red) for left bud, right bud, and case
- **ANC control** — switch between Off, Noise Cancellation, Transparency
- **EQ presets** — Balanced, More Bass, More Treble, Voice
- **In-ear detection toggle** — enable / disable the sensor
- **Real RFCOMM protocol** — binary packet format reverse-engineered from Nothing Ear firmware; activates automatically when a Nothing device is connected
- **Scan for new devices** — triggers BlueZ discovery for 30 s
- **Nothing X dark theme** — pure black, JetBrains Mono, white accents

---

## Device support

| Device | BT discovery | Battery | ANC | EQ |
|---|---|---|---|---|
| Nothing Ear (1) | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (2) | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (a) | ✅ | ✅ | ✅ | ✅ |
| Nothing Ear (stick) | ✅ | ✅ | — | ✅ |
| CMF Buds / Buds Pro | ✅ | ✅ | ✅ | ✅ |
| Nothing Phone (1/2) | ✅ | — | — | — |
| Other BT devices | ✅ | ✅ (if reported by BlueZ) | — | — |

> RFCOMM control (ANC / EQ) requires the device to be **connected** and within range. Battery readings come from BlueZ's `Battery1` interface — available after pairing on most Nothing earbuds.

---

## Requirements

### System (Arch / Omarchy)

```bash
sudo pacman -S python-gobject python-dbus gtk4 libadwaita
```

| Package | Purpose |
|---|---|
| `python-gobject` | GTK4, libadwaita, Cairo Python bindings |
| `python-dbus` | BlueZ D-Bus access |
| `gtk4` | UI toolkit |
| `libadwaita` | Adwaita widgets + dark theme |

### Python

```
PyGObject >= 3.42
dbus-python >= 1.3
```

---

## Installation

### Run from source (recommended on Omarchy)

```bash
git clone https://github.com/SoaOaoS/something-x
cd something-x
./somethingx
```

### Install as a command

```bash
pip install --user .
something-x
```

This installs the `something-x` command to `~/.local/bin/`.

### Desktop launcher

Copy the `.desktop` file so it appears in Walker / Rofi / your app launcher:

```bash
cp nothing_app/data/com.something.x.omarchy.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

---

## Usage

```
./nothingx          # launch
something-x         # if installed via pip
```

1. **Home page** — shows all paired Bluetooth devices. Nothing/CMF devices are labelled with a `NOTHING` badge.
2. **Scan** — tap "SCAN FOR DEVICES" to search for nearby unpaired devices (30 s window).
3. **Device page** — tap any device card to open its control panel:
   - Battery rings update in real time once RFCOMM connects
   - ANC and EQ buttons take effect immediately
4. **Disconnect** — the red button sends a clean BlueZ disconnect.

---

## Architecture

```
nothing_app/
├── application.py      GtkApplication, CSS loading, dark theme
├── window.py           AdwNavigationView — home ↔ device routing
├── bluetooth.py        BlueZ D-Bus manager (signals on connect/disconnect)
├── protocol.py         Nothing Ear RFCOMM binary protocol
├── data/
│   └── style.css       Nothing X CSS theme (bundled with package)
└── pages/
    ├── home.py         Device list + scan
    └── device.py       ANC / EQ / settings + Cairo earbud visual
```

---

## Contributing

The RFCOMM protocol in [nothing_app/protocol.py](nothing_app/protocol.py) is based on community reverse engineering. If your device uses different channel numbers or command IDs, patches are welcome.

---

## License

MIT
