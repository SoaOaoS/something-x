# Something X — Roadmap

---

## Known Issues

- Window control buttons (close/minimize/maximize) in the headerbar had a double-hover effect on non-tiling desktops due to app CSS overriding the system theme — fixed on `feat/fix-headerbar-window-controls`.

---

## v1.x — Near term

### Docs
- [x] **GitHub Pages** — project landing page + full documentation site (`docs/`)

### Distribution
- [x] AUR package — AUR package for Arch users to replace pip
- [x] **NixOS flake** — `flake.nix` for Nix users
- [x] **`.desktop` file** — ships and auto-installs so the app appears in Walker/Rofi/GNOME launcher

### Features
- [x] **Low battery desktop notification** — `notify-send` when any bud drops below 20 %
- [x] **Background mode** — closing the window hides it; relaunch shows it again (Gio single-instance)
- [x] **Per-device profiles** — ANC + EQ saved per device address to `~/.config/something-x/profiles.json`, restored automatically on reconnect
- [x] **CLI quick-toggle** — `something-x --anc off|on|transparency`, `something-x --eq bass`, `something-x --battery`
- [x] **System tray icon** — show battery on hover via StatusNotifierItem (Waybar/SNI)
- [x] **Wearing detection display** — show L/R in-ear status on the earbud visual
- [x] **Auto-connect RFCOMM** — connect as soon as BlueZ reports the device connected, no tap needed

### Fixes
- [x] **Headerbar button hover** — window controls now respect the system theme on all desktops

### Protocol
- [x] **Debug mode** — `SOMETHING_X_DEBUG=1` env var dumps raw RFCOMM frames for contributors
- [x] **Graceful ANC mode detection** — infer supported modes from RFCOMM level response; hide unsupported buttons

---

## v2.x — Medium term

### Features
- [ ] **Multiple devices simultaneously** — open two device pages, manage both at once
- [ ] **Quick-settings panel** — small floating overlay triggered by keybind
- [ ] **Touch controls remapping** — if the protocol exposes it (found in APK, not yet implemented)
- [ ] **Equalizer graph** — visual EQ curve instead of preset pills; custom presets with sliders
- [ ] **Firmware update check** — compare device firmware against latest known version, show badge

### Tech
- [x] **Async BlueZ** — replaced `dbus-python` with native `Gio` async D-Bus (non-blocking, no extra dependency)
- [x] **Unit tests** — 65 tests covering CRC, protocol parsing, battery dedup, profiles, and BluetoothManager

---

## v3.x — Long term / ideas

- [ ] **CMF Watch support** — different protocol; would need fresh APK reverse-engineering
- [ ] **Nothing Phone integration** — glyph control, notification mirroring
- [ ] **GNOME Shell extension** — battery indicator in the top bar
- [ ] **KDE Plasma widget** — same idea for KDE users
- [ ] **macOS port** — replace BlueZ D-Bus with CoreBluetooth via `pyobjc` (long shot)

---

## Won't do

- **Windows** — no BlueZ, RFCOMM access requires a different stack entirely
- **Wayland screenshot / screen capture control** — out of scope
- **Streaming / media playback control** — MPRIS already handles this system-wide

