from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, GLib, GObject, Gtk

from lumina.backend.pacman import PacmanError, load_installed_packages
from lumina.models.package import Package
from lumina.utils.format import format_count
from lumina.utils.threading import run_in_thread
from lumina.widgets.filter_bar import FilterBar
from lumina.widgets.operation_dialog import OperationDialog
from lumina.widgets.package_details import PackageDetails
from lumina.widgets.package_list import PackageList


class InstalledView(Gtk.Box):
    __gtype_name__ = "LuminaInstalledView"
    __gsignals__ = {
        "heading-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "filter-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "selection-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, initial_filter: str = "all", paned_position: int = 620) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._filter = initial_filter if initial_filter else "all"
        self._loading = False
        self._load_gen = 0
        self._selected_name: str | None = None
        self.filter_bar = FilterBar()
        self.filter_bar.set_mode(self._filter)
        self.filter_bar.connect_search(self._on_search)
        self.filter_bar.connect_filter(self._on_filter_dropdown)
        self.package_list = PackageList()
        self.package_list.set_mode(self._filter)
        self.package_list.connect("package-selected", self._on_package_selected)
        self.package_list.connect("count-changed", self._on_count_changed)
        self.details = PackageDetails()
        self.details.connect("remove-requested", lambda *_args: self.remove_selected())
        self.paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            start_child=self.package_list,
            end_child=self.details,
            resize_start_child=True,
            shrink_start_child=False,
            resize_end_child=False,
            shrink_end_child=False,
            hexpand=True,
            vexpand=True,
        )
        self.paned.set_position(paned_position)
        self.loading = self._status_box("Loading packages…", spinning=True)
        self.error_page = Adw.StatusPage(
            title="Could not load packages",
            icon_name="dialog-error-symbolic",
            vexpand=True,
        )
        retry = Gtk.Button(label="Try Again")
        retry.add_css_class("pill")
        retry.connect("clicked", lambda *_args: self.refresh())
        self.error_page.set_child(retry)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.loading, "loading")
        self.stack.add_named(self.paned, "content")
        self.stack.add_named(self.error_page, "error")
        self.append(self.filter_bar)
        self.append(self.stack)
        self._emit_heading("Loading…")

    def refresh(self) -> None:
        if self._loading:
            return
        selected = self.package_list.get_selected_package()
        self._selected_name = selected.name if selected else self._selected_name
        self._loading = True
        self._load_gen += 1
        generation = self._load_gen
        self.stack.set_visible_child_name("loading")
        self._emit_heading("Loading…")
        self.emit("selection-changed", False)

        def success(result: object) -> None:
            if generation != self._load_gen:
                return
            packages = result if isinstance(result, list) else []
            self.package_list.set_packages(packages)
            self.stack.set_visible_child_name("content")
            self._loading = False
            self._emit_heading()
            if self._selected_name:
                self.package_list.select_name(self._selected_name)
            self._on_package_selected()

        def failure(exc: BaseException) -> None:
            if generation != self._load_gen:
                return
            self._loading = False
            message = str(exc) if isinstance(exc, PacmanError) else f"Unexpected error: {exc}"
            self.error_page.set_description(GLib.markup_escape_text(message))
            self.stack.set_visible_child_name("error")
            self._emit_heading("Could not load packages")
            self.emit("selection-changed", False)

        run_in_thread(load_installed_packages, success, failure)

    def focus_search(self) -> None:
        self.filter_bar.focus_search()

    def get_filter(self) -> str:
        return self._filter

    def set_filter(self, mode: str) -> None:
        if mode == self._filter:
            self.filter_bar.set_mode(mode)
            return
        self._filter = mode
        self.filter_bar.set_mode(mode)
        self.package_list.set_mode(mode)
        self.emit("filter-changed", mode)
        self._emit_heading()

    def get_paned_position(self) -> int:
        return self.paned.get_position()

    def remove_selected(self) -> None:
        package = self.package_list.get_selected_package()
        if package is None or self._loading:
            return
        root = self.get_root()
        if not isinstance(root, Gtk.Widget):
            return
        dialog = OperationDialog(package, lambda code: self._on_operation_finished(code, package.name))
        dialog.present(root)

    def _on_operation_finished(self, code: int, name: str) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            if code == 0:
                root.show_toast(f"Removed {name}")
            else:
                root.show_toast(f"Could not remove {name}")
        if code == 0:
            self._selected_name = None
        self._loading = False
        self.refresh()

    def _on_search(self, query: str) -> None:
        self.package_list.set_query(query)

    def _on_filter_dropdown(self, mode: str) -> None:
        if mode == self._filter:
            return
        self._filter = mode
        self.package_list.set_mode(mode)
        self.emit("filter-changed", mode)
        self._emit_heading()

    def _on_package_selected(self, *_args: object) -> None:
        package = self.package_list.get_selected_package()
        self.details.show_package(package if isinstance(package, Package) else None)
        self._selected_name = package.name if package else None
        self.emit("selection-changed", package is not None)

    def _on_count_changed(self, _list: PackageList, shown: int, total: int) -> None:
        if self._loading:
            return
        self._emit_heading(format_count(shown, total))

    def _emit_heading(self, subtitle: str | None = None) -> None:
        titles = {"apps": "Apps", "orphans": "Orphans"}
        title = titles.get(self._filter, "Installed")
        if subtitle is None:
            shown = self.package_list.filtered.get_n_items()
            total = self.package_list.store.get_n_items()
            subtitle = format_count(shown, total) if total else ""
        self.emit("heading-changed", title, subtitle)

    def _status_box(self, text: str, *, spinning: bool) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        if spinning:
            spinner = Adw.Spinner()
            spinner.set_size_request(32, 32)
            box.append(spinner)
        box.append(Gtk.Label(label=text))
        return box
