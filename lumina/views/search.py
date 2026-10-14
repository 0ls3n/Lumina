from collections.abc import Callable

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, GLib, GObject, Gtk

from lumina.backend.aur import detect_helper
from lumina.backend.discover import load_discover
from lumina.backend.pacman import PacmanError, PreviewResult
from lumina.backend.search import SearchResult, clean_query, install_command, preview_install, search_packages
from lumina.utils.threading import run_in_thread
from lumina.widgets.command_dialog import CommandDialog
from lumina.widgets.discover import DiscoverBrowser
from lumina.widgets.icons import apply_app_icon

SCOPES = (
    ("both", "Official and AUR"),
    ("official", "Official repos"),
    ("aur", "AUR"),
)


class SearchView(Gtk.Box):
    __gtype_name__ = "LuminaSearchView"
    __gsignals__ = {
        "heading-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_packages_changed: Callable[[], None] | None = None
        self._timeout = 0
        self._generation = 0
        self._searching = False
        self._query = ""
        self._results: list[SearchResult] = []
        self._catalog_ready = False
        self._scope = "both" if detect_helper() else "official"

        bar = Gtk.Box(spacing=8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        self.entry = Gtk.SearchEntry(placeholder_text="Search packages to install", hexpand=True)
        self.entry.connect("search-changed", self._on_changed)
        self.entry.connect("activate", lambda *_args: self.search_now())
        labels = Gtk.StringList.new([label for _mode, label in SCOPES])
        self.scope = Gtk.DropDown(model=labels)
        self.scope.set_selected(0 if self._scope == "both" else 1)
        self.scope.connect("notify::selected", lambda *_args: self._on_scope())
        bar.append(self.entry)
        bar.append(self.scope)
        self.append(bar)

        self.warning = Gtk.Label(xalign=0, wrap=True)
        self.warning.add_css_class("warning-text")
        self.warning.add_css_class("caption")
        self.warning.set_margin_start(12)
        self.warning.set_margin_end(12)
        self.warning.set_margin_bottom(8)
        self.warning.set_visible(False)
        self.append(self.warning)

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_margin_start(12)
        self.listbox.set_margin_end(12)
        self.listbox.set_margin_bottom(12)
        scrolled = Gtk.ScrolledWindow(child=self.listbox, vexpand=True)
        self.discover = DiscoverBrowser(on_install=self.install)
        self.loading = Adw.StatusPage(title="Loading apps…", icon_name="system-search-symbolic", vexpand=True)
        spinner = Adw.Spinner()
        spinner.set_size_request(32, 32)
        self.loading.set_child(spinner)
        self.empty = Adw.StatusPage(
            title="No packages found",
            description="Try another name, or switch between official repositories and the AUR.",
            icon_name="edit-find-symbolic",
            vexpand=True,
        )
        self.error_page = Adw.StatusPage(title="Search failed", icon_name="dialog-error-symbolic", vexpand=True)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.discover, "discover")
        self.stack.add_named(self.loading, "loading")
        self.stack.add_named(scrolled, "list")
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.error_page, "error")
        self.append(self.stack)
        self.stack.set_visible_child_name("loading")
        self._load_catalog()

    def focus_search(self) -> None:
        self.entry.grab_focus()
        self.entry.select_region(0, -1)

    def announce(self) -> None:
        self._emit_heading()
        self.focus_search()

    def repeat(self) -> None:
        if self._query:
            self.search_now()

    def search_now(self) -> None:
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0
        query = self.entry.get_text()
        try:
            cleaned = clean_query(query)
        except PacmanError:
            self._query = ""
            self._results = []
            self._show_warning("")
            self._show_discover()
            return
        self._query = cleaned
        self._generation += 1
        generation = self._generation
        scope = self._scope
        self._searching = True
        self.stack.set_visible_child_name("loading")
        self._emit_heading("Searching…")

        def work() -> object:
            return search_packages(cleaned, scope=scope)

        def success(result: object) -> None:
            if generation != self._generation:
                return
            results, warning = result if isinstance(result, tuple) else ([], "")
            self._searching = False
            self._results = list(results)
            self._show_warning(str(warning))
            self._fill()
            self._emit_heading()

        def failure(exc: BaseException) -> None:
            if generation != self._generation:
                return
            self._searching = False
            message = str(exc) if isinstance(exc, PacmanError) else f"Unexpected error: {exc}"
            self.error_page.set_description(GLib.markup_escape_text(message))
            self.stack.set_visible_child_name("error")
            self._emit_heading("Search failed")

        run_in_thread(work, success, failure)

    def install(self, result: SearchResult) -> None:
        if result.installed:
            return
        source = "the AUR" if result.source == "aur" else result.repo
        summary = f"Download and install {result.name} {result.version} from {source}."
        if result.source == "aur":
            summary += " The build runs as your user. pkexec is only used for the pacman transaction."
        preview = None if result.source == "aur" else (lambda: preview_install(result.name))
        root = self.get_root()
        if not isinstance(root, Gtk.Widget):
            return
        dialog = CommandDialog(
            title=f"Install {result.name}",
            subtitle="pacman -S" if result.source == "official" else "AUR install",
            summary=summary,
            confirm_label="Install",
            build_argv=lambda: install_command(result.name, result.source),
            on_finished=lambda code: self._on_installed(code, result.name),
            preview=preview,
            preview_title="Will download",
        )
        if preview is None:
            dialog.preview_label.set_label(result.description or result.name)
        dialog.present(root)

    def _on_changed(self, _entry: Gtk.SearchEntry) -> None:
        if self._timeout:
            GLib.source_remove(self._timeout)
        text = self.entry.get_text().strip()
        if len(text) < 2:
            self._timeout = 0
            if not text:
                self.search_now()
            return
        self._timeout = GLib.timeout_add(350, self._debounced)

    def _debounced(self) -> bool:
        self._timeout = 0
        self.search_now()
        return False

    def _on_scope(self) -> None:
        index = self.scope.get_selected()
        if 0 <= index < len(SCOPES):
            self._scope = SCOPES[index][0]
        if self._query:
            self.search_now()

    def _on_installed(self, code: int, name: str) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            if code == 0:
                root.show_toast(f"Installed {name}")
            else:
                root.show_toast(f"Could not install {name}")
        if code == 0 and self.on_packages_changed is not None:
            self.on_packages_changed()
        if code == 0 and self.entry.get_text().strip():
            self.search_now()
        elif code == 0:
            self._load_catalog()

    def _fill(self) -> None:
        while child := self.listbox.get_row_at_index(0):
            self.listbox.remove(child)
        if not self._results:
            self.stack.set_visible_child_name("empty")
            return
        for result in self._results:
            self.listbox.append(self._row(result))
        self.stack.set_visible_child_name("list")

    def _row(self, result: SearchResult) -> Adw.ActionRow:
        row = Adw.ActionRow()
        image = Gtk.Image(valign=Gtk.Align.CENTER)
        apply_app_icon(image, result.name, 32, result.name)
        row.add_prefix(image)
        row.set_title(result.name)
        detail = f"{result.repo}  ·  {result.version}"
        if result.description:
            detail = f"{detail}  ·  {result.description}"
        row.set_subtitle(detail)
        if hasattr(row, "set_subtitle_lines"):
            row.set_subtitle_lines(2)
        if result.installed:
            badge = Gtk.Label(label="Installed")
            badge.add_css_class("caption")
            badge.add_css_class("dim-label")
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)
            return row
        button = Gtk.Button(label="Install")
        button.add_css_class("suggested-action")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda *_args, item=result: self.install(item))
        row.add_suffix(button)
        return row

    def _load_catalog(self) -> None:
        self._generation += 1
        generation = self._generation

        def success(result: object) -> None:
            if generation != self._generation or self._query:
                return
            sections = list(result) if isinstance(result, list) else []
            self.discover.set_sections(sections)
            self._catalog_ready = bool(sections)
            if not self._searching:
                self._show_discover()

        def failure(_exc: BaseException) -> None:
            if generation != self._generation or self._query:
                return
            self._catalog_ready = False
            if not self._searching:
                self.empty.set_description("Could not load suggested apps. Search for a package instead.")
                self.stack.set_visible_child_name("empty")
                self._emit_heading("Discover")

        run_in_thread(load_discover, success, failure)

    def _show_discover(self) -> None:
        if self._catalog_ready:
            self.stack.set_visible_child_name("discover")
        else:
            self.stack.set_visible_child_name("loading")
        self._emit_heading("Discover")

    def _show_warning(self, warning: str) -> None:
        self.warning.set_visible(bool(warning))
        self.warning.set_label(warning)

    def _emit_heading(self, subtitle: str | None = None) -> None:
        if subtitle is None:
            count = len(self._results)
            if not self._query:
                subtitle = "Discover"
            elif count == 1:
                subtitle = "1 result"
            else:
                subtitle = f"{count} results"
        self.emit("heading-changed", "Search", subtitle)
