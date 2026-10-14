from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gtk


def build_search_view() -> Gtk.Widget:
    return Adw.StatusPage(
        title="Search",
        description="Search official repositories and the AUR, then install from the results. Planned for the next release.",
        icon_name="system-search-symbolic",
        vexpand=True,
    )
