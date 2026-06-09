import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from .bluetooth import BluetoothDevice, BluetoothManager
from .pages.home import HomePage
from .pages.device import DevicePage


class SomethingXWindow(Adw.ApplicationWindow):
    def __init__(self, bt_manager: BluetoothManager, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(420, 780)
        self.set_resizable(True)
        self._bt = bt_manager
        self._build()

    def _build(self):
        nav = Adw.NavigationView()
        self.set_content(nav)
        self._nav = nav
        nav.push(self._make_home_nav_page())

    def _make_home_nav_page(self) -> Adw.NavigationPage:
        nav_page = Adw.NavigationPage()
        nav_page.set_tag("home")
        nav_page.set_title("Something X")

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.add_css_class("nothing-header")
        header.set_show_title(True)

        bt_btn = Gtk.Button.new_from_icon_name("bluetooth-symbolic")
        bt_btn.set_tooltip_text("Bluetooth settings")
        bt_btn.connect("clicked", self._open_bt_settings)
        header.pack_end(bt_btn)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh devices")
        refresh_btn.connect("clicked", lambda _: self._bt.refresh())
        header.pack_end(refresh_btn)

        toolbar_view.add_top_bar(header)

        home_page = HomePage(bt_manager=self._bt)
        home_page.connect("device-selected", self._on_device_selected)
        toolbar_view.set_content(home_page)

        nav_page.set_child(toolbar_view)
        return nav_page

    def _make_device_nav_page(self, bt_device: BluetoothDevice) -> Adw.NavigationPage:
        nav_page = Adw.NavigationPage()
        nav_page.set_tag("device")
        nav_page.set_title(bt_device.name)

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.add_css_class("nothing-header")
        toolbar_view.add_top_bar(header)

        device_page = DevicePage(bt_device=bt_device, bt_manager=self._bt)
        toolbar_view.set_content(device_page)

        nav_page.set_child(toolbar_view)
        nav_page.connect("hidden", lambda _: device_page.cleanup())
        return nav_page

    def _on_device_selected(self, _home, bt_device: BluetoothDevice):
        self._nav.push(self._make_device_nav_page(bt_device))

    def _open_bt_settings(self, _btn):
        import subprocess
        for cmd in (
            ["blueman-manager"],
            ["gnome-control-center", "bluetooth"],
            ["xdg-open", "settings://bluetooth"],
        ):
            try:
                subprocess.Popen(cmd, start_new_session=True)
                return
            except FileNotFoundError:
                continue
