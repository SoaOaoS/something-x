# Something X — Roadmap

---

## Portability

### Other Linux distros

The app runs on any Linux system with BlueZ. System package names vary:

| Distro | Install command |
|---|---|
| Arch / Omarchy | `sudo pacman -S python-gobject python-dbus python-cairo gtk4 libadwaita` |
| Ubuntu 24.04+ | `sudo apt install python3-gi python3-dbus python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1` |
| Fedora 39+ | `sudo dnf install python3-gobject python3-dbus python3-cairo gtk4 libadwaita` |
| openSUSE | `sudo zypper install python3-gobject python3-dbus python3-cairo gtk4 libadwaita` |
| NixOS | see `flake.nix` (planned, see below) |

Requirements: `bluetoothd` running, BlueZ ≥ 5.6, GTK4 ≥ 4.6, libadwaita ≥ 1.2.

Volume control requires `pactl` — available on any PulseAudio or PipeWire system.

### Nothing device compatibility

The RFCOMM `0x55` protocol is shared across the entire Nothing Ear lineup. Confirmed working on **Nothing Ear (2)**; the same activation sequence, ANC wire values, and EQ command IDs are present in the APK for all models listed below.

| Device | Protocol confirmed | Community reports |
|---|---|---|
| Nothing Ear (2) | ✅ reverse-engineered from APK | ✅ |
| Nothing Ear (1) | ✅ same APK protocol class | needs field testing |
| Nothing Ear (a) | ✅ same APK protocol class | needs field testing |
| Nothing Ear (stick) | ✅ (no ANC cmd) | needs field testing |
| CMF Buds / Buds Pro | ⚠️ likely same, different cmd IDs possible | needs field testing |
| Nothing Ear (open) | ❓ ANC not applicable | not yet tested |
| CMF Watch | ❓ different protocol expected | not started |

**If your device doesn't work:** open an issue with the raw RFCOMM dump (run with `SOMETHING_X_DEBUG=1 ./somethingx`).

---

## v1.x — Near term

### Distribution
- [x] AUR package - AUR Package for Arch user to replace pip 
- [x] **NixOS flake** — `flake.nix` for Nix users
- [x] **`.desktop` file** — ship and auto-install it so the app appears in Walker/Rofi/GNOME launcher

### Features
- [x] **Low battery desktop notification** — `notify-send` when any bud drops below 20 %
- [x] **Background mode** — closing the window hides it; relaunch shows it again (Gio single-instance)
- [x] **Per-device profiles** — ANC + EQ saved per device address to `~/.config/something-x/profiles.json`, restored automatically on reconnect
- [x] **CLI quick-toggle** — `something-x --anc off|on|transparency`, `something-x --eq bass`, `something-x --battery`
- [ ] **System tray icon** — show battery on hover via StatusNotifierItem (Waybar/SNI)
- [ ] **Wearing detection display** — show L/R in-ear status on the earbud visual
- [x] **Auto-connect RFCOMM** — connect as soon as BlueZ reports the device connected, no tap needed

### Protocol / devices
- [ ] **CMF Buds Pro field testing** — verify ANC command IDs match
- [ ] **Nothing Ear (1) / (a) field testing** — confirm ANC modes work
- [x] **Debug mode** — `SOMETHING_X_DEBUG=1` env var dumps raw RFCOMM frames for contributors
- [ ] **Graceful ANC mode detection** — query supported modes from device instead of hardcoding

---

## v2.x — Medium term

### Features
- [ ] **Multiple devices simultaneously** — open two device pages, manage both at once
- [ ] **Hyprland integration** — waybar module that shows battery % and ANC state
- [ ] **Quick-settings panel** — a small floating overlay (like Nothing's quick tile) triggered by keybind
- [ ] **Touch controls remapping** — if the protocol exposes it (found in APK, not yet implemented)
- [ ] **Equalizer graph** — visual EQ curve instead of preset pills; custom presets with sliders
- [ ] **Firmware update check** — compare device firmware against latest known version, show badge

### Tech
- [ ] **Async BlueZ** — replace `dbus-python` with `dbus-fast` for non-blocking I/O
- [ ] **Persistent state** — remember last ANC/EQ per device across app restarts (`~/.config/something-x/`)
- [ ] **Unit tests** — protocol encode/decode, CRC, ANC mode mapping

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
