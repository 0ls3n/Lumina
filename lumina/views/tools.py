from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gtk


def build_tools_view() -> Gtk.Widget:
    return Adw.StatusPage(
        title="Tools",
        description="Orphaned packages are already listed under Orphans. Cache cleaning and other maintenance actions are planned for a later release.",
        icon_name="applications-system-symbolic",
        vexpand=True,
    )
