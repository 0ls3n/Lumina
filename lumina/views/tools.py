from collections.abc import Callable

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, GLib, GObject, Gtk

from lumina.backend.maintenance import (
    DiskReport,
    MaintenanceSnapshot,
    clean_all_cache_command,
    clean_unused_cache_command,
    disk_segments,
    load_maintenance,
    preview_orphan_removal,
    remove_orphans_command,
)
from lumina.backend.pacman import PacmanError
from lumina.utils.format import format_size
from lumina.utils.threading import run_in_thread
from lumina.widgets.command_dialog import CommandDialog
from lumina.widgets.storage_bar import StorageBar


class ToolsView(Gtk.Box):
    __gtype_name__ = "LuminaToolsView"
    __gsignals__ = {
        "heading-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_packages_changed: Callable[[], None] | None = None
        self.on_show_orphans: Callable[[], None] | None = None
        self._loading = False
        self._loaded = False
        self._generation = 0
        self._snapshot: MaintenanceSnapshot | None = None
        self._orphans_expanded = False

        self.loading = Adw.StatusPage(title="Checking maintenance…", icon_name="applications-system-symbolic", vexpand=True)
        spinner = Adw.Spinner()
        spinner.set_size_request(32, 32)
        self.loading.set_child(spinner)
        self.error_page = Adw.StatusPage(title="Could not check maintenance", icon_name="dialog-error-symbolic", vexpand=True)
        retry = Gtk.Button(label="Try Again")
        retry.add_css_class("pill")
        retry.connect("clicked", lambda *_args: self.refresh())
        self.error_page.set_child(retry)
        self.content = Gtk.ScrolledWindow(vexpand=True)
        self.page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.page.set_margin_start(12)
        self.page.set_margin_end(12)
        self.page.set_margin_top(12)
        self.page.set_margin_bottom(16)
        self.content.set_child(self.page)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.loading, "loading")
        self.stack.add_named(self.content, "content")
        self.stack.add_named(self.error_page, "error")
        self.append(self.stack)

    def ensure_loaded(self) -> None:
        if not self._loaded and not self._loading:
            self.refresh()
            return
        self._emit_heading()

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._generation += 1
        generation = self._generation
        self.stack.set_visible_child_name("loading")
        self._emit_heading("Checking…")

        def success(result: object) -> None:
            if generation != self._generation:
                return
            self._loading = False
            self._loaded = True
            self._snapshot = result if isinstance(result, MaintenanceSnapshot) else None
            self._orphans_expanded = False
            self._fill()
            self._emit_heading()

        def failure(exc: BaseException) -> None:
            if generation != self._generation:
                return
            self._loading = False
            self._loaded = True
            message = str(exc) if isinstance(exc, PacmanError) else f"Unexpected error: {exc}"
            self.error_page.set_description(GLib.markup_escape_text(message))
            self.stack.set_visible_child_name("error")
            self._emit_heading("Could not check")

        run_in_thread(load_maintenance, success, failure)

    def _fill(self) -> None:
        while child := self.page.get_first_child():
            self.page.remove(child)
        snapshot = self._snapshot
        if snapshot is None:
            return
        self.page.append(self._storage_group(snapshot))
        self.page.append(self._orphans_group(snapshot))
        self.page.append(self._cache_group(snapshot))
        self.stack.set_visible_child_name("content")

    def _storage_group(self, snapshot: MaintenanceSnapshot) -> Gtk.Widget:
        disk = snapshot.disk
        group = Adw.PreferencesGroup(title="Storage")
        group.set_description(f"{format_size(disk.free_bytes)} free of {format_size(disk.total_bytes)}")
        bar_row = Gtk.ListBoxRow(selectable=False, activatable=False)
        bar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bar_box.set_margin_top(6)
        bar_box.set_margin_bottom(6)
        bar_box.set_margin_start(12)
        bar_box.set_margin_end(12)
        bar = StorageBar()
        bar.set_hexpand(True)
        bar.set_segments(disk_segments(disk))
        bar_box.append(bar)
        bar_box.append(self._legend())
        note = Gtk.Label(
            label="Apps are installed packages. Files are your home folder. Other is the rest of the disk.",
            xalign=0,
            wrap=True,
        )
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        bar_box.append(note)
        bar_row.set_child(bar_box)
        group.add(bar_row)
        group.add(self._swatch_row("Free", format_size(disk.free_bytes), "storage-free"))
        group.add(self._swatch_row("Apps", format_size(disk.apps_bytes), "storage-apps"))
        group.add(self._swatch_row("Files", _files_label(disk), "storage-files"))
        group.add(self._swatch_row("Package cache", format_size(disk.cache_bytes), "storage-cache"))
        group.add(self._swatch_row("Other", format_size(disk_segments(disk)[3][1]), "storage-other"))
        return group

    def _legend(self) -> Gtk.Box:
        row = Gtk.Box(spacing=12)
        row.set_margin_top(2)
        for title, css in (
            ("Apps", "storage-apps"),
            ("Files", "storage-files"),
            ("Cache", "storage-cache"),
            ("Other", "storage-other"),
            ("Free", "storage-free"),
        ):
            item = Gtk.Box(spacing=6)
            swatch = Gtk.Box()
            swatch.add_css_class("storage-swatch")
            swatch.add_css_class(css)
            swatch.set_size_request(10, 10)
            swatch.set_valign(Gtk.Align.CENTER)
            label = Gtk.Label(label=title)
            label.add_css_class("caption")
            item.append(swatch)
            item.append(label)
            row.append(item)
        return row

    def _swatch_row(self, title: str, value: str, css: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=value)
        swatch = Gtk.Box()
        swatch.add_css_class("storage-swatch")
        swatch.add_css_class(css)
        swatch.set_size_request(12, 12)
        row.add_prefix(swatch)
        return row

    def _orphans_group(self, snapshot: MaintenanceSnapshot) -> Gtk.Widget:
        count = len(snapshot.orphans)
        group = Adw.PreferencesGroup(title="Orphaned packages")
        group.set_description(
            "Installed as dependencies, but nothing needs them anymore."
            if count
            else "No orphaned packages."
        )
        if count:
            shown = snapshot.orphans if self._orphans_expanded or count <= 5 else snapshot.orphans[:5]
            for orphan in shown:
                group.add(Adw.ActionRow(title=orphan.name, subtitle=orphan.version))
        actions = Gtk.Box(spacing=8)
        actions.set_margin_top(8)
        remove = Gtk.Button(label="Remove orphans")
        remove.add_css_class("destructive-action")
        remove.set_sensitive(count > 0)
        remove.connect("clicked", lambda *_args: self._remove_orphans())
        view = Gtk.Button(label="Show in package list")
        view.connect("clicked", lambda *_args: self._show_orphans())
        actions.append(remove)
        actions.append(view)
        if count > 5:
            extra = count - 5
            toggle = Gtk.Button(label="Show less" if self._orphans_expanded else f"View all ({extra} more)")
            toggle.connect("clicked", lambda *_args: self._toggle_orphans())
            actions.append(toggle)
        group.add(self._action_row(actions))
        return group

    def _cache_group(self, snapshot: MaintenanceSnapshot) -> Gtk.Widget:
        cache = snapshot.cache
        group = Adw.PreferencesGroup(title="Package cache")
        if not cache.readable:
            group.set_description("The cache directory is not readable. Cleaning still runs as root.")
        else:
            group.set_description(
                "Unused cache is the estimated size of downloaded packages that are no longer installed."
            )
        group.add(self._info_row("Total cache", format_size(cache.total_bytes) if cache.readable else "—"))
        group.add(self._info_row("Unused cache", format_size(cache.unused_bytes) if cache.readable else "—"))
        group.add(self._info_row("Cached files", f"{cache.file_count:,}" if cache.readable else "—"))
        if not snapshot.paccache:
            group.add(self._info_row("paccache", "Not installed. Using pacman -Sc and -Scc."))
        actions = Gtk.Box(spacing=8)
        actions.set_margin_top(8)
        unused = Gtk.Button(label="Remove unused cache")
        unused.connect("clicked", lambda *_args: self._clean_unused())
        unused.set_sensitive(not cache.readable or cache.unused_bytes > 0)
        clear = Gtk.Button(label="Clear entire cache")
        clear.add_css_class("destructive-action")
        clear.connect("clicked", lambda *_args: self._clean_all())
        actions.append(unused)
        actions.append(clear)
        group.add(self._action_row(actions))
        return group

    def _info_row(self, title: str, value: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=value)
        if hasattr(row, "set_subtitle_selectable"):
            row.set_subtitle_selectable(True)
        return row

    def _action_row(self, actions: Gtk.Widget) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(selectable=False, activatable=False)
        row.set_child(actions)
        return row

    def _remove_orphans(self) -> None:
        snapshot = self._snapshot
        if snapshot is None or not snapshot.orphans:
            return
        names = [orphan.name for orphan in snapshot.orphans]
        self._present(
            title="Remove orphaned packages",
            subtitle="pacman -Rns",
            summary="This removes packages that are no longer required, including dependencies that become unused. Removed packages are not kept in the cache.",
            confirm_label="Remove",
            build_argv=lambda: remove_orphans_command(names),
            preview=lambda: preview_orphan_removal(names),
            preview_title="Will remove",
            destructive=True,
        )

    def _clean_unused(self) -> None:
        snapshot = self._snapshot
        size = format_size(snapshot.cache.unused_bytes) if snapshot and snapshot.cache.readable else "an unknown amount"
        self._present(
            title="Remove unused cache",
            subtitle="pacman -Sc",
            summary=f"This deletes cached downloads for packages that are not installed. About {size} can be freed. Installed package files stay in the cache.",
            confirm_label="Clean",
            build_argv=clean_unused_cache_command,
            static_preview=f"Estimated unused cache: {size}",
            destructive=True,
        )

    def _clean_all(self) -> None:
        snapshot = self._snapshot
        size = format_size(snapshot.cache.total_bytes) if snapshot and snapshot.cache.readable else "the entire cache"
        self._present(
            title="Clear package cache",
            subtitle="pacman -Scc",
            summary=f"This deletes every cached package, including copies of installed packages ({size}). Reinstalling or downgrading later will download them again.",
            confirm_label="Clear cache",
            build_argv=clean_all_cache_command,
            static_preview=f"Entire cache: {size}",
            destructive=True,
        )

    def _present(
        self,
        *,
        title: str,
        subtitle: str,
        summary: str,
        confirm_label: str,
        build_argv: Callable[[], list[str]],
        preview: Callable[[], object] | None = None,
        preview_title: str = "What will happen",
        static_preview: str = "",
        destructive: bool = False,
    ) -> None:
        root = self.get_root()
        if not isinstance(root, Gtk.Widget):
            return
        dialog = CommandDialog(
            title=title,
            subtitle=subtitle,
            summary=summary,
            confirm_label=confirm_label,
            build_argv=build_argv,
            on_finished=self._on_finished,
            preview=preview,
            preview_title=preview_title,
            destructive=destructive,
        )
        if preview is None and static_preview:
            dialog.preview_label.set_label(static_preview)
        dialog.present(root)

    def _on_finished(self, code: int) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            root.show_toast("Finished" if code == 0 else "The tool did not finish successfully")
        if code == 0 and self.on_packages_changed is not None:
            self.on_packages_changed()
        self._loading = False
        self.refresh()

    def _toggle_orphans(self) -> None:
        self._orphans_expanded = not self._orphans_expanded
        self._fill()

    def _show_orphans(self) -> None:
        if self.on_show_orphans is not None:
            self.on_show_orphans()

    def _emit_heading(self, subtitle: str | None = None) -> None:
        if subtitle is None:
            snapshot = self._snapshot
            if snapshot is None:
                subtitle = ""
            else:
                count = len(snapshot.orphans)
                orphan_text = "1 orphan" if count == 1 else f"{count} orphans"
                subtitle = f"{format_size(snapshot.disk.free_bytes)} free · {orphan_text}"
        self.emit("heading-changed", "Tools", subtitle)


def _files_label(disk: DiskReport) -> str:
    if disk.files_bytes is None:
        return "Unavailable"
    label = format_size(disk.files_bytes)
    if not disk.files_on_disk:
        return f"{label} (separate disk)"
    return label
