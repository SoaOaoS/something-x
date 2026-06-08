import sys
import importlib.resources
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk, Gio

from .bluetooth import BluetoothManager
from .window import SomethingXWindow


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
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._load_css()
        self._bt = BluetoothManager()
        win = SomethingXWindow(bt_manager=self._bt, application=self)
        win.present()

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


def main():
    app = SomethingXApplication()
    sys.exit(app.run(sys.argv))
