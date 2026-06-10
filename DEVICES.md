# Something X — Device & Platform Compatibility

---

## Supported devices

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

## Linux distros

The app runs on any Linux system with BlueZ. System package names vary:

| Distro | Install command |
|---|---|
| Arch / Omarchy | `sudo pacman -S python-gobject python-dbus python-cairo gtk4 libadwaita` |
| Ubuntu 24.04+ | `sudo apt install python3-gi python3-dbus python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1` |
| Fedora 39+ | `sudo dnf install python3-gobject python3-dbus python3-cairo gtk4 libadwaita` |
| openSUSE | `sudo zypper install python3-gobject python3-dbus python3-cairo gtk4 libadwaita` |
| NixOS | see `flake.nix` |

Requirements: `bluetoothd` running, BlueZ ≥ 5.6, GTK4 ≥ 4.6, libadwaita ≥ 1.2.

Volume control requires `pactl` — available on any PulseAudio or PipeWire system.
