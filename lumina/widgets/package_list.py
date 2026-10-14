from lumina import gi_init

gi_init.ensure()

from gi.repository import Gio, GObject, Gtk, Pango

from lumina.models.package import Package
from lumina.utils.format import format_size
from lumina.utils.search import package_visible
from lumina.widgets.icons import apply_app_icon


class PackageItem(GObject.Object):
    __gtype_name__ = "LuminaPackageItem"

    def __init__(self, package: Package) -> None:
        super().__init__()
        self.package = package


class PackageRow(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(spacing=12)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.icon = Gtk.Image(valign=Gtk.Align.CENTER)
        self.icon.set_visible(False)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        top = Gtk.Box(spacing=8)
        self.name = Gtk.Label(xalign=0, hexpand=True)
        self.name.add_css_class("heading")
        self.name.set_ellipsize(Pango.EllipsizeMode.END)
        self.badge = Gtk.Label()
        self.badge.add_css_class("caption")
        self.badge.add_css_class("package-badge")
        self.badge.set_halign(Gtk.Align.END)
        self.badge.set_valign(Gtk.Align.CENTER)
        top.append(self.name)
        top.append(self.badge)
        self.meta = Gtk.Label(xalign=0)
        self.meta.add_css_class("dim-label")
        self.meta.add_css_class("caption")
        self.meta.set_ellipsize(Pango.EllipsizeMode.END)
        text.append(top)
        text.append(self.meta)
        self.append(self.icon)
        self.append(text)

    def set_package(self, package: Package) -> None:
        title = package.app_name or package.name
        self.name.set_label(title)
        if package.app_name:
            self.icon.set_visible(True)
            apply_app_icon(self.icon, package.app_icon, 40)
        else:
            self.icon.set_visible(False)
        self.badge.set_label(package.badge)
        self.badge.remove_css_class("official")
        self.badge.remove_css_class("foreign")
        self.badge.remove_css_class("local")
        self.badge.add_css_class(package.badge_style)
        parts = [package.version, format_size(package.installed_size)]
        if package.app_name and package.app_name.casefold() != package.name.casefold():
            parts.insert(0, package.name)
        if package.orphan:
            parts.append("orphan")
        self.meta.set_label("  ·  ".join(parts))


class PackageList(Gtk.Box):
    __gtype_name__ = "LuminaPackageList"
    __gsignals__ = {
        "package-selected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "count-changed": (GObject.SignalFlags.RUN_FIRST, None, (int, int)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._query = ""
        self._mode = "all"
        self.store = Gio.ListStore.new(PackageItem)
        self.filter = Gtk.CustomFilter.new(self._match)
        self.filtered = Gtk.FilterListModel.new(self.store, self.filter)
        self.filtered.connect("items-changed", self._on_items_changed)
        self.selection = Gtk.SingleSelection.new(self.filtered)
        self.selection.set_autoselect(False)
        self.selection.connect("selection-changed", self._on_selection_changed)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        self.listview = Gtk.ListView(model=self.selection, factory=factory)
        self.listview.set_show_separators(True)
        self.listview.set_vexpand(True)
        scrolled = Gtk.ScrolledWindow(child=self.listview, hexpand=True, vexpand=True)
        self.empty = Gtk.Label(label="No packages match this search or filter.", wrap=True)
        self.empty.add_css_class("dim-label")
        self.empty.set_margin_top(24)
        self.empty.set_margin_bottom(24)
        self.stack = Gtk.Stack()
        self.stack.add_named(scrolled, "list")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

    def set_packages(self, packages: list[Package]) -> None:
        self.store.remove_all()
        for package in packages:
            self.store.append(PackageItem(package))
        self._refresh_filter()

    def set_query(self, query: str) -> None:
        self._query = query
        self._refresh_filter()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        if mode == "apps":
            self.empty.set_label("No applications match. Use All installed to see every package.")
        else:
            self.empty.set_label("No packages match this search or filter.")
        self._refresh_filter()

    def get_selected_package(self) -> Package | None:
        item = self.selection.get_selected_item()
        if item is None:
            return None
        return item.package

    def select_name(self, name: str) -> None:
        count = self.filtered.get_n_items()
        for index in range(count):
            item = self.filtered.get_item(index)
            if item is not None and item.package.name == name:
                self.selection.set_selected(index)
                return
        self.selection.set_selected(Gtk.INVALID_LIST_POSITION)

    def _match(self, item: PackageItem, *_args: object) -> bool:
        return package_visible(item.package, self._query, self._mode)

    def _refresh_filter(self) -> None:
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._emit_count()

    def _on_items_changed(self, *_args: object) -> None:
        self._emit_count()

    def _emit_count(self) -> None:
        shown = self.filtered.get_n_items()
        total = self.store.get_n_items()
        self.stack.set_visible_child_name("list" if shown else "empty")
        self.emit("count-changed", shown, total)

    def _on_selection_changed(self, *_args: object) -> None:
        self.emit("package-selected")

    def _setup(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        list_item.set_child(PackageRow())

    def _bind(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        row = list_item.get_child()
        if isinstance(item, PackageItem) and isinstance(row, PackageRow):
            row.set_package(item.package)
