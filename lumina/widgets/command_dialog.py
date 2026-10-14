import shlex
from collections.abc import Callable

from lumina import gi_init

gi_init.ensure()

from gi.repository import Adw, Gtk, Pango

from lumina.backend.pacman import PacmanError, PreviewResult
from lumina.backend.runner import ProcessRunner
from lumina.utils.threading import idle, run_in_thread


class CommandDialog(Adw.Dialog):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        summary: str,
        confirm_label: str,
        build_argv: Callable[[], list[str]],
        on_finished: Callable[[int], None],
        preview: Callable[[], PreviewResult] | None = None,
        preview_title: str = "Packages",
    ) -> None:
        super().__init__()
        self._build_argv = build_argv
        self._on_finished = on_finished
        self._preview = preview
        self._preview_gen = 0
        self._preview_ok = preview is None
        self._argv: list[str] | None = None
        self._running = False
        self._finished = False
        self._runner = ProcessRunner()
        self.set_title(title)
        self.set_content_width(560)
        self.set_content_height(520)
        self._title = title
        self._subtitle = subtitle
        self._summary = summary
        self._confirm_label = confirm_label
        self._preview_title = preview_title
        self._build()
        self._refresh_command()
        if preview is None:
            self.preview_label.set_label(summary)
            self.preview_spinner.set_spinning(False)
        else:
            self._schedule_preview()

    def _build(self) -> None:
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=self._title, subtitle=self._subtitle))
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        summary = Gtk.Label(label=self._summary, xalign=0, wrap=True)
        content.append(summary)

        preview_header = Gtk.Box(spacing=8)
        preview_label = Gtk.Label(label=self._preview_title, xalign=0, hexpand=True)
        preview_label.add_css_class("heading")
        self.preview_spinner = Gtk.Spinner(spinning=self._preview is not None)
        preview_header.append(preview_label)
        preview_header.append(self.preview_spinner)
        content.append(preview_header)
        self.preview_label = Gtk.Label(label="Checking…", xalign=0, wrap=True, selectable=True)
        self.preview_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        preview_scroll = Gtk.ScrolledWindow(child=self.preview_label)
        preview_scroll.set_min_content_height(72)
        preview_scroll.set_max_content_height(160)
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
        copy.add_css_class("flat")
        copy.set_valign(Gtk.Align.START)
        copy.set_tooltip_text("Copy command")
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

        toolbar.set_content(Gtk.ScrolledWindow(child=content, vexpand=True))
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        actions.set_margin_start(12)
        actions.set_margin_end(12)
        actions.set_margin_top(8)
        actions.set_margin_bottom(8)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", self._on_cancel)
        self.confirm_button = Gtk.Button(label=self._confirm_label)
        self.confirm_button.add_css_class("suggested-action")
        self.confirm_button.connect("clicked", self._on_confirm)
        actions.append(self.cancel_button)
        actions.append(self.confirm_button)
        toolbar.add_bottom_bar(actions)
        self.set_child(toolbar)
        self.connect("closed", self._on_closed)

    def _refresh_command(self) -> None:
        try:
            argv = self._build_argv()
        except PacmanError as exc:
            self.command.set_label(str(exc))
            self._argv = None
            self.buffer_note.set_label("")
            self._update_actions()
            return
        self._argv = argv
        self.command.set_label(shlex.join(argv))
        if any(part == "stdbuf" or part.endswith("/stdbuf") for part in argv):
            self.buffer_note.set_label("stdbuf is included so output appears as it is produced.")
        else:
            self.buffer_note.set_label("")
        self._update_actions()

    def _schedule_preview(self) -> None:
        if self._preview is None:
            return
        self._preview_gen += 1
        generation = self._preview_gen
        self.preview_spinner.set_spinning(True)
        self._preview_ok = False
        self._update_actions()

        def success(result: object) -> None:
            if generation != self._preview_gen:
                return
            self.preview_spinner.set_spinning(False)
            preview = result if isinstance(result, PreviewResult) else PreviewResult(False, [], "No preview.")
            self._preview_ok = preview.ok
            lines = list(preview.targets[:40])
            extra = len(preview.targets) - len(lines)
            if extra > 0:
                lines.append(f"… and {extra} more")
            if not preview.ok:
                lines.insert(0, preview.message or "The preview failed.")
                self.preview_label.add_css_class("warning-text")
            elif not lines:
                lines = ["Nothing pending in the current databases. The command will still sync and apply new updates."]
            self.preview_label.set_label("\n".join(lines))
            self._update_actions()

        def failure(exc: BaseException) -> None:
            if generation != self._preview_gen:
                return
            self.preview_spinner.set_spinning(False)
            self._preview_ok = False
            self.preview_label.set_label(str(exc))
            self.preview_label.add_css_class("warning-text")
            self._update_actions()

        run_in_thread(self._preview, success, failure)

    def _update_actions(self) -> None:
        if self._running or self._finished:
            return
        self.confirm_button.set_sensitive(self._argv is not None and self._preview_ok)

    def _copy_command(self, *_args: object) -> None:
        self.get_clipboard().set(self.command.get_label())

    def _on_confirm(self, *_args: object) -> None:
        if not self._argv or self._running:
            return
        self._running = True
        self._preview_gen += 1
        self.confirm_button.set_sensitive(False)
        self.log_box.set_visible(True)
        if self._argv and self._argv[0].endswith("pkexec"):
            self._append("Waiting for authorization…\n")
        else:
            self._append("Running…\n")
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
        self.confirm_button.set_visible(False)
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
