from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, GLib, GObject, Gtk

from lumina.models.package import Package
from lumina.utils.format import format_size
from lumina.widgets.icons import apply_app_icon


class PackageDetails(Gtk.Box):
    __gtype_name__ = "LuminaPackageDetails"
    __gsignals__ = {
        "remove-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_size_request(300, -1)
        self.stack = Gtk.Stack()
        self.empty = Adw.StatusPage(
            title="No package selected",
            description="Choose a package to see what it is and why it is installed.",
            icon_name="package-x-generic-symbolic",
            vexpand=True,
        )
        self.scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scrolled.set_propagate_natural_width(True)
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.scrolled, "package")
        self.append(self.stack)
        self.show_package(None)

    def show_package(self, package: Package | None) -> None:
        if package is None:
            self.stack.set_visible_child_name("empty")
            return
        self.scrolled.set_child(self._build(package))
        self.stack.set_visible_child_name("package")

    def _build(self, package: Package) -> Gtk.Box:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_start(16)
        root.set_margin_end(16)
        root.set_margin_top(16)
        root.set_margin_bottom(16)

        if package.orphan:
            banner = Gtk.Label(label="Orphaned package — nothing depends on it", xalign=0, wrap=True)
            banner.add_css_class("caption")
            banner.add_css_class("warning-text")
            root.append(banner)

        title_row = Gtk.Box(spacing=12)
        if package.app_name:
            icon = Gtk.Image(valign=Gtk.Align.CENTER)
            apply_app_icon(icon, package.app_icon, 48)
            title_row.append(icon)
        name = Gtk.Label(label=package.app_name or package.name, xalign=0, hexpand=True, wrap=True)
        name.add_css_class("title-2")
        name.set_selectable(True)
        badge = Gtk.Label(label=package.badge)
        badge.add_css_class("package-badge")
        badge.add_css_class(package.badge_style)
        badge.set_valign(Gtk.Align.CENTER)
        title_row.append(name)
        title_row.append(badge)
        root.append(title_row)

        description = Gtk.Label(
            label=package.description or "No description",
            xalign=0,
            wrap=True,
            selectable=True,
        )
        root.append(description)

        remove = Gtk.Button(label="Remove package")
        remove.add_css_class("destructive-action")
        remove.set_halign(Gtk.Align.START)
        remove.connect("clicked", lambda *_args: self.emit("remove-requested"))
        root.append(remove)

        info = Adw.PreferencesGroup(title="Details")
        origin = package.repo or package.badge
        if package.origin.value == "foreign":
            origin = "Foreign (AUR or locally built)"
        elif package.origin.value == "local":
            origin = "Local (repository database has no match)"
        if package.app_name and package.app_name.casefold() != package.name.casefold():
            info.add(self._row("Application", package.app_name))
        info.add(self._row("Origin", origin))
        info.add(self._row("Version", package.version))
        info.add(self._row("Installed size", format_size(package.installed_size)))
        info.add(self._row("Architecture", package.architecture or "—"))
        info.add(self._row("Licenses", ", ".join(package.licenses) or "—"))
        info.add(self._row("Install reason", package.reason_label))
        if package.install_date:
            info.add(self._row("Installed", package.install_date.strftime("%Y-%m-%d %H:%M")))
        if package.packager:
            info.add(self._row("Packager", package.packager))
        if package.validated_by:
            info.add(self._row("Validated by", package.validated_by))
        if package.url:
            info.add(self._row("Homepage", package.url))
        root.append(info)

        if package.url:
            links = Adw.PreferencesGroup(title="Links")
            link = Gtk.LinkButton(uri=package.url, label="Open homepage")
            link.set_halign(Gtk.Align.START)
            holder = Gtk.ListBoxRow(selectable=False, activatable=False)
            holder.set_child(link)
            links.add(holder)
            root.append(links)

        relations = Adw.PreferencesGroup(title="Relations")
        relations.add(self._list_row("Depends on", package.depends))
        relations.add(self._list_row("Required by", package.required_by))
        relations.add(self._list_row("Optional dependencies", package.optional_deps))
        if package.provides:
            relations.add(self._list_row("Provides", package.provides))
        if package.conflicts:
            relations.add(self._list_row("Conflicts", package.conflicts))
        if package.groups:
            relations.add(self._list_row("Groups", package.groups))
        root.append(relations)
        return root

    def _row(self, title: str, value: str) -> Gtk.Widget:
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(value or "—"))
        if hasattr(row, "set_subtitle_selectable"):
            row.set_subtitle_selectable(True)
        return row

    def _list_row(self, title: str, items: list[str]) -> Gtk.Widget:
        if not items:
            return self._row(title, "None")
        if len(items) <= 4 and sum(len(item) for item in items) < 120:
            return self._row(title, ", ".join(items))
        row = Adw.ExpanderRow()
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(str(len(items)))
        label = Gtk.Label(label="\n".join(items), xalign=0, wrap=True, selectable=True)
        label.set_margin_top(6)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        holder = Gtk.ListBoxRow(selectable=False, activatable=False)
        holder.set_child(label)
        row.add_row(holder)
        return row
