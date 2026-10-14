from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gtk


def build_updates_view() -> Gtk.Widget:
    return Adw.StatusPage(
        title="Updates",
        description="Pending updates and system upgrade will show the exact pacman command before anything runs. Planned for the next release.",
        icon_name="software-update-available-symbolic",
        vexpand=True,
    )
