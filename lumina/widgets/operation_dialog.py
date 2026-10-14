import shlex

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gtk, Pango

from lumina.backend.pacman import CRITICAL_PACKAGES, PacmanError, preview_remove, remove_command
from lumina.backend.runner import ProcessRunner
from lumina.models.package import Package
from lumina.utils.threading import idle, run_in_thread


class OperationDialog(Adw.Dialog):
    def __init__(self, package: Package, on_finished) -> None:
        super().__init__()
        self.package = package
        self._on_finished = on_finished
        self._recursive = False
        self._preview_gen = 0
        self._preview_ok = False
        self._argv: list[str] | None = None
        self._running = False
        self._finished = False
        self._runner = ProcessRunner()
        self.set_title(f"Remove {package.name}")
        self.set_content_width(560)
        self.set_content_height(520)
        self._build()
        self._refresh_command()
        self._schedule_preview()

    def _build(self) -> None:
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=f"Remove {self.package.name}", subtitle="pacman -R"))
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        summary = Gtk.Label(
            label="The command below is exactly what will run after you confirm. Authentication may be requested.",
            xalign=0,
            wrap=True,
        )
        content.append(summary)

        self.warning = Gtk.Label(xalign=0, wrap=True)
        self.warning.add_css_class("warning-text")
        self.warning.set_visible(self.package.name in CRITICAL_PACKAGES)
        if self.package.name in CRITICAL_PACKAGES:
            self.warning.set_label(
                "This is a critical system package. Removing it can make the system unusable."
            )
        content.append(self.warning)

        self.ack = Gtk.CheckButton(label="I understand this may break the system")
        self.ack.set_visible(self.package.name in CRITICAL_PACKAGES)
        self.ack.connect("toggled", lambda *_args: self._update_actions())
        content.append(self.ack)

        self.recursive = Gtk.CheckButton(label="Also remove dependencies that are no longer needed (-Rs)")
        self.recursive.connect("toggled", self._on_recursive_toggled)
        content.append(self.recursive)

        preview_header = Gtk.Box(spacing=8)
        preview_label = Gtk.Label(label="Packages that will be removed", xalign=0, hexpand=True)
        preview_label.add_css_class("heading")
        self.preview_spinner = Gtk.Spinner()
        preview_header.append(preview_label)
        preview_header.append(self.preview_spinner)
        content.append(preview_header)

        self.preview_label = Gtk.Label(label="Checking…", xalign=0, wrap=True, selectable=True)
        self.preview_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        preview_scroll = Gtk.ScrolledWindow(child=self.preview_label, vexpand=False)
        preview_scroll.set_min_content_height(72)
        preview_scroll.set_max_content_height(140)
        preview_scroll.set_propagate_natural_height(True)
        content.append(preview_scroll)

        command_label = Gtk.Label(label="Command", xalign=0)
        command_label.add_css_class("heading")
        content.append(command_label)
        self.command = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.command.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.command.add_css_class("command-preview")
        command_row = Gtk.Box(spacing=6)
        command_row.append(self.command)
        copy = Gtk.Button(icon_name="edit-copy-symbolic")
        copy.set_tooltip_text("Copy command")
        copy.add_css_class("flat")
        copy.set_valign(Gtk.Align.START)
        copy.connect("clicked", self._copy_command)
        command_row.append(copy)
        content.append(command_row)
        self.buffer_note = Gtk.Label(xalign=0, wrap=True)
        self.buffer_note.add_css_class("dim-label")
        self.buffer_note.add_css_class("caption")
        content.append(self.buffer_note)

        self.log_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.log_view.add_css_class("operation-log")
        self.log_buffer = self.log_view.get_buffer()
        log_scroll = Gtk.ScrolledWindow(child=self.log_view, vexpand=True)
        log_scroll.set_min_content_height(140)
        self.log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        log_title = Gtk.Label(label="Output", xalign=0)
        log_title.add_css_class("heading")
        self.log_box.append(log_title)
        self.log_box.append(log_scroll)
        self.log_box.set_visible(False)
        content.append(self.log_box)

        scrolled = Gtk.ScrolledWindow(child=content, vexpand=True)
        toolbar.set_content(scrolled)

        actions = Gtk.Box(spacing=8)
        actions.set_halign(Gtk.Align.END)
        actions.set_margin_start(12)
        actions.set_margin_end(12)
        actions.set_margin_top(8)
        actions.set_margin_bottom(8)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", self._on_cancel)
        self.remove_button = Gtk.Button(label="Remove")
        self.remove_button.add_css_class("destructive-action")
        self.remove_button.connect("clicked", self._on_remove)
        actions.append(self.cancel_button)
        actions.append(self.remove_button)
        toolbar.add_bottom_bar(actions)
        self.set_child(toolbar)
        self.connect("closed", self._on_closed)

    def _on_recursive_toggled(self, button: Gtk.CheckButton) -> None:
        self._recursive = button.get_active()
        self._refresh_command()
        self._schedule_preview()

    def _refresh_command(self) -> None:
        try:
            argv = remove_command([self.package.name], recursive=self._recursive)
        except PacmanError as exc:
            self.command.set_label(str(exc))
            self._argv = None
            self.buffer_note.set_label("")
            self._update_actions()
            return
        self._argv = argv
        self.command.set_label(shlex.join(argv))
        if any(part == "stdbuf" or part.endswith("/stdbuf") for part in argv):
            self.buffer_note.set_label("stdbuf is included so pacman output appears as it is produced.")
        else:
            self.buffer_note.set_label("")
        self._update_actions()

    def _schedule_preview(self) -> None:
        self._preview_gen += 1
        generation = self._preview_gen
        recursive = self._recursive
        self.preview_spinner.set_spinning(True)
        self.preview_label.set_label("Checking…")
        self._preview_ok = False
        self._update_actions()

        def work() -> object:
            return preview_remove([self.package.name], recursive=recursive)

        def success(result: object) -> None:
            if generation != self._preview_gen:
                return
            self.preview_spinner.set_spinning(False)
            preview = result
            self._preview_ok = bool(getattr(preview, "ok", False))
            targets = list(getattr(preview, "targets", []))
            message = str(getattr(preview, "message", ""))
            shown = targets[:40]
            extra = len(targets) - len(shown)
            if self._preview_ok:
                text = "\n".join(shown) if shown else self.package.name
                if extra > 0:
                    text += f"\n… and {extra} more"
                self.preview_label.set_label(text)
                self.preview_label.remove_css_class("warning-text")
            else:
                lines = [message] if message else ["pacman refused this removal."]
                lines.extend(shown)
                if extra > 0:
                    lines.append(f"… and {extra} more")
                self.preview_label.set_label("\n".join(lines))
                self.preview_label.add_css_class("warning-text")
            self._update_actions()

        def failure(exc: BaseException) -> None:
            if generation != self._preview_gen:
                return
            self.preview_spinner.set_spinning(False)
            self._preview_ok = False
            self.preview_label.set_label(str(exc))
            self.preview_label.add_css_class("warning-text")
            self._update_actions()

        run_in_thread(work, success, failure)

    def _update_actions(self) -> None:
        if self._running or self._finished:
            return
        acknowledged = (not self.ack.get_visible()) or self.ack.get_active()
        self.remove_button.set_sensitive(self._argv is not None and self._preview_ok and acknowledged)

    def _copy_command(self, *_args: object) -> None:
        display = GdkClipboard(self)
        if display is not None:
            display.set(self.command.get_label())

    def _on_remove(self, *_args: object) -> None:
        if not self._argv or self._running:
            return
        self._running = True
        self._preview_gen += 1
        self.remove_button.set_sensitive(False)
        self.recursive.set_sensitive(False)
        self.ack.set_sensitive(False)
        self.cancel_button.set_label("Cancel")
        self.log_box.set_visible(True)
        self._append("Waiting for authorization…\n")
        self._runner.start(self._argv, self._on_line, self._on_exit)

    def _on_line(self, line: str) -> None:
        idle(self._append, line)

    def _on_exit(self, code: int) -> None:
        idle(self._complete, code)

    def _append(self, text: str) -> None:
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, text)
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self.log_view.scroll_mark_onscreen(mark)

    def _complete(self, code: int) -> None:
        self._running = False
        self._finished = True
        if code == 0:
            self._append("\nFinished successfully.\n")
        elif code < 0:
            self._append("\nThe operation did not start.\n")
        else:
            self._append(f"\nFinished with status {code}.\n")
        self.cancel_button.set_label("Close")
        self.remove_button.set_visible(False)
        if self._on_finished is not None:
            self._on_finished(code)

    def _on_cancel(self, *_args: object) -> None:
        if self._running:
            self._append("\nCancel requested. A privileged process may keep running.\n")
            self._runner.cancel()
            self.cancel_button.set_sensitive(False)
            return
        self.close()

    def _on_closed(self, *_args: object) -> None:
        self._preview_gen += 1
        if self._running:
            self._runner.cancel()


def GdkClipboard(widget: Gtk.Widget):
    clipboard = widget.get_clipboard()
    return clipboard
