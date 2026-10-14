import sys

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gio

from lumina import APP_ID
from lumina.utils.preferences import Preferences
from lumina.window import LuminaWindow


class LuminaApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self._on_activate)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_args: self.quit())
        self.add_action(quit_action)
        self._set_accels()

    def _set_accels(self) -> None:
        self.set_accels_for_action("win.update-system", ["<primary>u"])
        self.set_accels_for_action("win.refresh", ["F5"])
        self.set_accels_for_action("win.remove", ["Delete"])
        self.set_accels_for_action("win.focus-search", ["<primary>f"])
        self.set_accels_for_action("win.shortcuts", ["<primary>question"])
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def _on_activate(self, _app: Adw.Application) -> None:
        window = self.props.active_window
        if window is None:
            window = LuminaWindow(application=self, prefs=Preferences.load())
        window.present()


def main() -> int:
    app = LuminaApplication()
    return app.run(sys.argv)
