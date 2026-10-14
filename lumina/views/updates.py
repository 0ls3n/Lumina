from collections.abc import Callable

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, GLib, GObject, Gtk

from lumina.backend.aur import helper_status
from lumina.backend.pacman import PacmanError, PreviewResult
from lumina.backend.updates import (
    PendingUpdate,
    load_pending_updates,
    package_update_command,
    preview_official_upgrades,
    sync_command,
    system_update_command,
)
from lumina.utils.threading import run_in_thread
from lumina.widgets.command_dialog import CommandDialog


class UpdatesView(Gtk.Box):
    __gtype_name__ = "LuminaUpdatesView"
    __gsignals__ = {
        "heading-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "count-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_packages_changed: Callable[[], None] | None = None
        self._loading = False
        self._load_gen = 0
        self._updates: list[PendingUpdate] = []
        self._loaded = False

        actions = Gtk.Box(spacing=8)
        actions.set_margin_start(12)
        actions.set_margin_end(12)
        actions.set_margin_top(12)
        actions.set_margin_bottom(6)
        self.update_button = Gtk.Button(label="Update system")
        self.update_button.add_css_class("suggested-action")
        self.update_button.connect("clicked", lambda *_args: self.update_system())
        self.sync_button = Gtk.Button(label="Sync databases")
        self.sync_button.connect("clicked", lambda *_args: self.sync_databases())
        actions.append(self.update_button)
        actions.append(self.sync_button)
        self.append(actions)

        note = Gtk.Label(label=helper_status(), xalign=0)
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.set_margin_bottom(8)
        self.append(note)

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
        self.empty = Adw.StatusPage(
            title="Up to date",
            description="No pending updates in the current databases. Sync databases if this list looks stale, or run a system update to refresh and upgrade.",
            icon_name="emblem-ok-symbolic",
            vexpand=True,
        )
        self.loading = Adw.StatusPage(title="Checking for updates…", icon_name="software-update-available-symbolic", vexpand=True)
        spinner = Adw.Spinner()
        spinner.set_size_request(32, 32)
        self.loading.set_child(spinner)
        self.error_page = Adw.StatusPage(title="Could not check updates", icon_name="dialog-error-symbolic", vexpand=True)
        retry = Gtk.Button(label="Try Again")
        retry.add_css_class("pill")
        retry.connect("clicked", lambda *_args: self.refresh())
        self.error_page.set_child(retry)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.loading, "loading")
        self.stack.add_named(scrolled, "list")
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.error_page, "error")
        self.append(self.stack)
        self.stack.set_visible_child_name("empty")

    def ensure_loaded(self) -> None:
        if not self._loaded and not self._loading:
            self.refresh()
            return
        if self._loading:
            self._emit_heading("Checking…")
            return
        self._emit_heading()

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._load_gen += 1
        generation = self._load_gen
        self.stack.set_visible_child_name("loading")
        self._emit_heading("Checking…")

        def success(result: object) -> None:
            if generation != self._load_gen:
                return
            updates, warning = result if isinstance(result, tuple) else ([], "")
            self._updates = list(updates)
            self._loaded = True
            self._loading = False
            self._show_warning(str(warning))
            self._fill()
            self._emit_heading()

        def failure(exc: BaseException) -> None:
            if generation != self._load_gen:
                return
            self._loading = False
            self._loaded = True
            message = str(exc) if isinstance(exc, PacmanError) else f"Unexpected error: {exc}"
            self.error_page.set_description(GLib.markup_escape_text(message))
            self.stack.set_visible_child_name("error")
            self._emit_heading("Could not check")
            self.emit("count-changed", 0)

        run_in_thread(load_pending_updates, success, failure)

    def update_system(self) -> None:
        helper = helper_status()
        aur = [item.label for item in self._updates if item.source == "aur"]
        uses_helper = "AUR helper:" in helper
        summary = (
            "This upgrades official packages and AUR packages. "
            "AUR builds run as your user. pkexec is only used for the pacman transaction."
            if uses_helper
            else "This runs pacman -Syu. You may be asked to authenticate."
        )
        subtitle = f"{helper.split(': ', 1)[-1]} -Syu" if uses_helper else "pacman -Syu"

        def preview() -> PreviewResult:
            official = preview_official_upgrades()
            targets = list(official.targets)
            targets.extend(aur)
            return PreviewResult(ok=official.ok, targets=targets, message=official.message)

        self._present(
            title="Update system",
            subtitle=subtitle,
            summary=summary,
            confirm_label="Update",
            build_argv=system_update_command,
            preview=preview,
        )

    def sync_databases(self) -> None:
        self._present(
            title="Sync databases",
            subtitle="pacman -Sy",
            summary="This refreshes the package databases without installing anything. You may be asked to authenticate.",
            confirm_label="Sync",
            build_argv=sync_command,
            preview=None,
            preview_title="What will happen",
            static_preview="Refresh official repository databases, then check for updates again.",
        )

    def update_package(self, update: PendingUpdate) -> None:
        if update.source == "aur":
            summary = (
                f"Build and install {update.name} {update.new_version} with the AUR helper. "
                "The build runs as your user."
            )
            subtitle = "AUR update"
        else:
            summary = f"Install {update.name} {update.new_version}, replacing {update.old_version}."
            subtitle = "pacman -S"
        self._present(
            title=f"Update {update.name}",
            subtitle=subtitle,
            summary=summary,
            confirm_label="Update",
            build_argv=lambda: package_update_command(update),
            preview=None,
            preview_title="Package",
            static_preview=update.label,
        )

    def _present(
        self,
        *,
        title: str,
        subtitle: str,
        summary: str,
        confirm_label: str,
        build_argv: Callable[[], list[str]],
        preview: Callable[[], PreviewResult] | None,
        preview_title: str = "Will upgrade",
        static_preview: str = "",
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
        )
        if preview is None and static_preview:
            dialog.preview_label.set_label(static_preview)
        dialog.present(root)

    def _on_finished(self, code: int) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            if code == 0:
                root.show_toast("Update finished")
            else:
                root.show_toast("Update did not finish successfully")
        if code == 0 and self.on_packages_changed is not None:
            self.on_packages_changed()
        self._loading = False
        self.refresh()

    def _fill(self) -> None:
        while child := self.listbox.get_row_at_index(0):
            self.listbox.remove(child)
        if not self._updates:
            self.stack.set_visible_child_name("empty")
            return
        for update in self._updates:
            self.listbox.append(self._row(update))
        self.stack.set_visible_child_name("list")

    def _row(self, update: PendingUpdate) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(update.name)
        row.set_subtitle(f"{update.old_version}  →  {update.new_version}")
        badge = Gtk.Label(label="AUR" if update.source == "aur" else "official")
        badge.add_css_class("caption")
        badge.add_css_class("dim-label")
        button = Gtk.Button(label="Update")
        button.add_css_class("suggested-action")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda *_args, item=update: self.update_package(item))
        row.add_suffix(badge)
        row.add_suffix(button)
        return row

    def _show_warning(self, warning: str) -> None:
        self.warning.set_visible(bool(warning))
        self.warning.set_label(warning)

    def _emit_heading(self, subtitle: str | None = None) -> None:
        count = len(self._updates)
        if subtitle is None:
            if count == 0:
                subtitle = "Up to date"
            elif count == 1:
                subtitle = "1 update"
            else:
                subtitle = f"{count} updates"
        self.emit("heading-changed", "Updates", subtitle)
        self.emit("count-changed", count if subtitle != "Checking…" else count)
