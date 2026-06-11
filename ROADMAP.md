# Something X — Roadmap

---

## Current release — v1.8

### Shipped
- [x] **GitHub Pages** — project landing page + full documentation site (`docs/`)
- [x] **AUR package** — Arch users can install without pip
- [x] **NixOS flake** — `flake.nix` for Nix users
- [x] **`.desktop` file** — ships and auto-installs so the app appears in Walker/Rofi/GNOME launcher
- [x] **Low battery notification** — `notify-send` when any bud drops below 20 %
- [x] **Background mode** — closing the window hides it; relaunch shows it again (Gio single-instance)
- [x] **Per-device profiles** — ANC + EQ saved per device address to `~/.config/something-x/profiles.json`, restored on reconnect
- [x] **CLI quick-toggle** — `something-x --anc off|on|transparency`, `something-x --eq bass`, `something-x --battery`
- [x] **System tray icon** — battery on hover via StatusNotifierItem (Waybar/SNI)
- [x] **Wearing detection display** — L/R in-ear status shown on the earbud visual
- [x] **Auto-connect RFCOMM** — connects as soon as BlueZ reports the device connected
- [x] **Async BlueZ** — native `Gio` async D-Bus, no `dbus-python` dependency
- [x] **Unit tests** — 65 tests covering CRC, protocol parsing, battery dedup, profiles, BluetoothManager
- [x] **Debug mode** — `SOMETHING_X_DEBUG=1` dumps raw RFCOMM frames for contributors
- [x] **Graceful ANC mode detection** — infer supported modes from RFCOMM response; hide unsupported buttons
- [x] **Dynamic versioning** — version sourced from git tags at build time
- [x] **Liquid glass dark UI** — overhauled aesthetic for the app window

---

## 1.9 — Quality of life

### Features
- [x] **Device nickname** — rename a paired device in the UI; stored in profiles
- [x] **Profile import / export** — share `.json` profile files between machines or with other users
- [ ] **Wear-detect MPRIS actions** — pause media when both buds are removed; resume when reinserted (opt-in)
- [x] **Notification preferences** — per-event toggles (battery low, connect, disconnect) in settings
- [ ] **Theming** — user-selectable accent color and light/dark mode toggle; theme stored in config

### Tech
- [x] **Improved test coverage** — profiles round-trip, nickname, notify prefs, notification gating (91 tests total)

---

## 1.10 — Desktop integration

### Features
- [ ] **D-Bus API** — expose ANC, EQ, battery, and connect/disconnect over a session-bus interface so scripts and status bars can consume it without spawning a CLI process
- [ ] **Global keybind support** — register a configurable shortcut (e.g. `Super+F1`) to cycle ANC modes without opening the window
- [ ] **Quick-settings overlay** — small floating panel triggered by keybind or tray click; ANC toggle + battery at a glance
- [ ] **Waybar module documentation** — sample `custom/somethingx` block wired to the D-Bus API

---

## 1.11 — Multi-device

### Features
- [ ] **Multiple devices simultaneously** — open a page per device, manage both at once without switching
- [ ] **Battery overview** — compact summary card on the home page showing all connected devices and their battery levels

---

## 1.12 — EQ overhaul

### Features
- [ ] **Visual EQ graph** — interactive SVG/Cairo curve instead of preset pills
- [ ] **Custom EQ presets** — per-band sliders, save with a user-defined name, stored in profiles
- [ ] **Preset sharing** — export / import individual EQ presets as `.json`

---

## 1.13 — Protocol depth

### Features
- [ ] **Touch controls remapping** — reassign tap/hold actions if the protocol exposes it (command IDs found in APK, not yet wired up)
- [ ] **Firmware version display** — read firmware string from RFCOMM and show it in the device page
- [ ] **Firmware update check** — compare device firmware against latest known version, show a badge when outdated

### Protocol / devices
- [ ] **CMF Buds / Buds Pro validation** — confirm command IDs and ship explicit support
- [ ] **Nothing Ear (1) / (a) / (stick) community testing** — collect field reports, fix edge cases
- [ ] **Structured debug logger** — `SOMETHING_X_DEBUG=1` writes a structured `.jsonl` capture file for easier issue reproduction

---

## 1.14 — Additional devices

### Features
- [ ] **Nothing Ear (open) support** — ANC not applicable; validate battery and EQ commands
- [ ] **CMF Watch support** — separate protocol; requires fresh APK reverse-engineering
- [ ] **Nothing Phone glyph integration** — notification mirroring and glyph lighting (depends on BlueZ + glyph API availability)

---

## Long term / ideas

These have no version target yet — they need either upstream work, a contributor, or significant scoping.

- [ ] **GNOME Shell extension** — battery indicator in the GNOME top bar
- [ ] **KDE Plasma widget** — same idea for KDE users
- [ ] **macOS port** — replace BlueZ D-Bus with CoreBluetooth via `pyobjc` (long shot)
- [ ] **Battery history graph** — plot battery level over time, persisted across sessions

---

## Won't do

- **Windows** — no BlueZ; RFCOMM access requires a completely different stack
- **Wayland screen capture control** — out of scope
- **Streaming / media playback control** — MPRIS already handles this system-wide
