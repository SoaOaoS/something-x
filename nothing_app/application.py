import os
import shutil
import subprocess
import sys
import importlib.resources
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from .bluetooth import BluetoothManager
from .window import SomethingXWindow
from .splash import SplashScreen


def _install_desktop_file():
    dest_dir = os.path.expanduser("~/.local/share/applications")
    dest = os.path.join(dest_dir, "com.something.x.omarchy.desktop")
    if os.path.exists(dest):
        return
    try:
        ref = importlib.resources.files("nothing_app.data").joinpath("com.something.x.omarchy.desktop")
        os.makedirs(dest_dir, exist_ok=True)
        with importlib.resources.as_file(ref) as src:
            shutil.copy2(src, dest)
        subprocess.run(["update-desktop-database", dest_dir], capture_output=True)
        print("[app] desktop file installed to ~/.local/share/applications/")
    except Exception as exc:
        print(f"[app] desktop file install skipped: {exc}")


def _css_path() -> str:
    try:
        ref = importlib.resources.files("nothing_app.data").joinpath("style.css")
        return str(ref)
    except Exception:
        import os
        return os.path.join(os.path.dirname(__file__), "data", "style.css")


class SomethingXApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.something.x.omarchy",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._bt: BluetoothManager | None = None
        self._splash: SplashScreen | None = None
        self._window: SomethingXWindow | None = None
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app):
        # Second launch while already running: just show the existing window
        if self._window is not None:
            self._window.present()
            return

        _install_desktop_file()
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._load_css()
        self._bt = BluetoothManager()
        splash = SplashScreen(on_done=self._on_splash_done)
        splash.set_application(self)
        self._splash = splash
        splash.present()
        splash.start()

    def _on_splash_done(self):
        win = SomethingXWindow(bt_manager=self._bt, application=self)
        win.connect("close-request", self._on_window_close)
        self._window = win
        win.present()
        if self._splash:
            self._splash.destroy()
            self._splash = None

    def _on_window_close(self, _win):
        # Hide instead of destroy so the app keeps running in background
        self._window.hide()
        subprocess.Popen(
            ["notify-send", "-i", "audio-headphones", "Something X",
             "Running in background. Launch again to reopen."],
            start_new_session=True,
        )
        return True  # prevent default close/destroy

    def _load_css(self):
        provider = Gtk.CssProvider()
        css = _css_path()
        try:
            provider.load_from_path(css)
        except Exception as exc:
            print(f"[app] CSS load failed ({css}): {exc}")

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )


# ── CLI quick-toggle mode ─────────────────────────────────────────────────────

_ANC_ALIASES = {
    "off": 0, "0": 0,
    "on": 1, "anc": 1, "noise": 1,
    "transparency": 2, "trans": 2, "passthrough": 2,
}

_EQ_ALIASES = {
    "balanced": "Balanced",
    "bass": "More Bass",
    "treble": "More Treble",
    "voice": "Voice",
}


def _run_cli(argv: list[str]) -> int:
    from . import protocol as _proto
    _proto._QUIET = True
    from .protocol import NothingDevice, ANCMode
    from . import profiles

    address = None
    if "--device" in argv:
        idx = argv.index("--device")
        if idx + 1 < len(argv):
            address = argv[idx + 1]

    if address is None:
        address = profiles.get_last_device()

    if address is None:
        print(
            "No known device. Open the GUI and connect to a device first,\n"
            "or pass --device AA:BB:CC:DD:EE:FF.",
            file=sys.stderr,
        )
        return 1

    loop = GLib.MainLoop()
    dev = NothingDevice(address)
    exit_code = [0]
    _acted = [False]

    def _act():
        if _acted[0]:
            return False
        _acted[0] = True

        if "--battery" in argv:
            s = dev.state
            parts = []
            if s.left_battery >= 0:
                parts.append(f"Left: {s.left_battery}%")
            if s.right_battery >= 0:
                parts.append(f"Right: {s.right_battery}%")
            if s.case_battery >= 0:
                parts.append(f"Case: {s.case_battery}%")
            print("  ".join(parts) if parts else "No battery data received.")

        if "--anc" in argv:
            idx = argv.index("--anc")
            val = argv[idx + 1] if idx + 1 < len(argv) else ""
            mode = _ANC_ALIASES.get(val.lower())
            if mode is None:
                print(f"Unknown ANC value '{val}'. Use: off, on, transparency", file=sys.stderr)
                exit_code[0] = 1
            else:
                dev.set_anc_mode(mode)
                print(f"ANC → {ANCMode.LABELS.get(mode)}")

        if "--eq" in argv:
            idx = argv.index("--eq")
            val = argv[idx + 1] if idx + 1 < len(argv) else ""
            preset = _EQ_ALIASES.get(val.lower())
            if preset is None:
                print(f"Unknown EQ preset '{val}'. Use: balanced, bass, treble, voice", file=sys.stderr)
                exit_code[0] = 1
            else:
                dev.set_eq_preset(preset)
                print(f"EQ → {preset}")

        GLib.timeout_add(600, loop.quit)
        return False

    def _on_state_changed(_d):
        if dev.state.left_battery >= 0 or dev.state.right_battery >= 0:
            _act()

    def _on_timeout():
        print("Timeout: device did not respond in time.", file=sys.stderr)
        exit_code[0] = 1
        loop.quit()
        return False

    dev.connect("state-changed", _on_state_changed)
    dev.connect_rfcomm()
    GLib.timeout_add(12000, _on_timeout)
    loop.run()
    dev.disconnect_rfcomm()
    return exit_code[0]


def _print_help():
    print(
        "Usage:\n"
        "  something-x                             launch GUI\n"
        "  something-x --battery                   print battery levels\n"
        "  something-x --anc off|on|transparency   set ANC mode\n"
        "  something-x --eq balanced|bass|treble|voice  set EQ preset\n"
        "  something-x --device AA:BB:CC:DD:EE:FF  target specific device\n"
    )


def main():
    argv = sys.argv[1:]
    cli_flags = {"--battery", "--anc", "--eq"}

    if "--help" in argv or "-h" in argv:
        _print_help()
        sys.exit(0)

    if any(f in argv for f in cli_flags):
        sys.exit(_run_cli(argv))

    app = SomethingXApplication()
    sys.exit(app.run(sys.argv))
