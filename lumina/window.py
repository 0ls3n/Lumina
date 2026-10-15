import shutil
import subprocess
from pathlib import Path

from lumina import APP_ID, gi_init

gi_init.ensure()

from gi.repository import Adw, Gdk, Gio, Gtk

from lumina import APP_NAME, __version__
from lumina.backend.aur import detect_helper, helper_status
from lumina.utils.preferences import Preferences
from lumina.views.installed import InstalledView
from lumina.views.search import SearchView
from lumina.views.tools import ToolsView
from lumina.views.updates import UpdatesView

NAV_ITEMS = (
    ("apps", "Apps", "view-app-grid-symbolic"),
    ("installed", "Installed", "view-list-symbolic"),
    ("updates", "Updates", "software-update-available-symbolic"),
    ("search", "Search", "system-search-symbolic"),
    ("orphans", "Orphans", "user-trash-symbolic"),
    ("tools", "Tools", "applications-system-symbolic"),
)


class LuminaWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, prefs: Preferences) -> None:
        super().__init__(application=application)
        self.prefs = prefs
        self.helper = detect_helper()
        self._syncing_nav = False
        self.set_title(APP_NAME)
        install_app_icon()
        self.set_icon_name(APP_ID)
        Gtk.Window.set_default_icon_name(APP_ID)
        self.set_default_size(prefs.width, prefs.height)
        self._load_css()
        self._build()
        self._add_actions()
        self.connect("close-request", self._on_close)
        self.installed.refresh()
        self.updates.refresh()

    def _build(self) -> None:
        self.toast = Adw.ToastOverlay()
        split = Adw.NavigationSplitView()
        split.set_min_sidebar_width(200)
        split.set_max_sidebar_width(260)
        split.set_sidebar_width_fraction(0.22)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Adw.WindowTitle(title=APP_NAME, subtitle="Arch packages"))
        self.nav = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.nav.add_css_class("navigation-sidebar")
        self.nav.connect("row-selected", self._on_nav_selected)
        self.rows: dict[str, Gtk.ListBoxRow] = {}
        self.nav_counts: dict[str, Gtk.Label] = {}
        for page_id, title, icon_name in NAV_ITEMS:
            row = self._nav_row(page_id, title, icon_name)
            self.rows[page_id] = row
            self.nav.append(row)
        footer = Gtk.Label(label=helper_status(), xalign=0)
        footer.add_css_class("dim-label")
        footer.add_css_class("caption")
        footer.add_css_class("sidebar-footer")
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        sidebar_box.append(self.nav)
        sidebar_box.append(footer)
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_toolbar.add_top_bar(sidebar_header)
        sidebar_toolbar.set_content(sidebar_box)

        self.title = Adw.WindowTitle(title="Installed", subtitle="")
        content_header = Adw.HeaderBar()
        content_header.set_title_widget(self.title)
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh (F5)")
        self.refresh_button.connect("clicked", self._refresh)
        self.update_button = Gtk.Button(label="Update system")
        self.update_button.add_css_class("suggested-action")
        self.update_button.set_tooltip_text("Upgrade all installed packages")
        self.update_button.connect("clicked", self._update_system)
        self.remove_button = Gtk.Button(label="Remove")
        self.remove_button.add_css_class("destructive-action")
        self.remove_button.set_sensitive(False)
        self.remove_button.set_tooltip_text("Remove selected package")
        self.remove_button.connect("clicked", lambda *_args: self.installed.remove_selected())
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self._menu())
        menu_button.set_tooltip_text("Menu")
        content_header.pack_end(menu_button)
        content_header.pack_end(self.remove_button)
        content_header.pack_end(self.refresh_button)
        content_header.pack_end(self.update_button)

        self.installed = InstalledView(self.prefs.filter, self.prefs.paned_position)
        self.installed.connect("heading-changed", self._on_heading_changed)
        self.installed.connect("filter-changed", self._on_filter_changed)
        self.installed.connect("selection-changed", self._on_selection_changed)
        self.updates = UpdatesView()
        self.updates.connect("heading-changed", self._on_updates_heading)
        self.updates.connect("count-changed", self._on_update_count)
        self.updates.on_packages_changed = self.installed.refresh
        self.search = SearchView()
        self.search.connect("heading-changed", self._on_search_heading)
        self.search.on_packages_changed = self.installed.refresh
        self.tools = ToolsView()
        self.tools.connect("heading-changed", self._on_tools_heading)
        self.tools.on_packages_changed = self.installed.refresh
        self.tools.on_show_orphans = self._show_orphans
        self.stack = Gtk.Stack()
        self.stack.add_named(self.installed, "installed")
        self.stack.add_named(self.updates, "updates")
        self.stack.add_named(self.search, "search")
        self.stack.add_named(self.tools, "tools")
        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(content_header)
        content_toolbar.set_content(self.stack)

        split.set_sidebar(Adw.NavigationPage.new(sidebar_toolbar, APP_NAME))
        split.set_content(Adw.NavigationPage.new(content_toolbar, "Installed"))
        self.toast.set_child(split)
        self.set_content(self.toast)

        self._syncing_nav = True
        initial = {"orphans": "orphans", "apps": "apps"}.get(self.prefs.filter, "installed")
        self.nav.select_row(self.rows[initial])
        self._syncing_nav = False

    def _nav_row(self, page_id: str, title: str, icon_name: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_name(page_id)
        box = Gtk.Box(spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(Gtk.Image.new_from_icon_name(icon_name))
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        count = Gtk.Label()
        count.add_css_class("caption")
        count.add_css_class("dim-label")
        count.set_visible(False)
        box.append(label)
        box.append(count)
        self.nav_counts[page_id] = count
        row.set_child(box)
        return row

    def _menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("Update system", "win.update-system")
        menu.append("Keyboard Shortcuts", "win.shortcuts")
        menu.append("About Lumina", "win.about")
        menu.append("Quit", "app.quit")
        return menu

    def _add_actions(self) -> None:
        self._action("update-system", self._update_system)
        self._action("refresh", self._refresh)
        self._action("remove", self._remove)
        self._action("focus-search", self._focus_search)
        self._action("shortcuts", self._show_shortcuts)
        self._action("about", self._show_about)

    def _action(self, name: str, callback) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def _on_nav_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self._syncing_nav or row is None:
            return
        page_id = row.get_name() or "installed"
        installed_actions = page_id in ("apps", "installed", "orphans")
        self.refresh_button.set_visible(installed_actions or page_id in ("updates", "search", "tools"))
        self.remove_button.set_visible(installed_actions)
        if page_id == "apps":
            self.stack.set_visible_child_name("installed")
            self.installed.set_filter("apps")
            self.installed.announce_heading()
            return
        if page_id == "orphans":
            self.stack.set_visible_child_name("installed")
            self.installed.set_filter("orphans")
            self.installed.announce_heading()
            return
        if page_id == "installed":
            self.stack.set_visible_child_name("installed")
            if self.installed.get_filter() in ("orphans", "apps"):
                self.installed.set_filter("all")
            self.installed.announce_heading()
            return
        if page_id == "updates":
            self.stack.set_visible_child_name("updates")
            self.updates.ensure_loaded()
            return
        if page_id == "search":
            self.stack.set_visible_child_name("search")
            self.search.announce()
            return
        if page_id == "tools":
            self.stack.set_visible_child_name("tools")
            self.tools.ensure_loaded()
            return
        self.stack.set_visible_child_name(page_id)

    def _show_orphans(self) -> None:
        self._syncing_nav = True
        self.nav.select_row(self.rows["orphans"])
        self._syncing_nav = False
        self.stack.set_visible_child_name("installed")
        self.refresh_button.set_visible(True)
        self.remove_button.set_visible(True)
        self.installed.set_filter("orphans")
        self.installed.announce_heading()

    def _on_tools_heading(self, _view: ToolsView, title: str, subtitle: str) -> None:
        if self.stack.get_visible_child_name() != "tools":
            return
        self.title.set_title(title)
        self.title.set_subtitle(subtitle)

    def _on_search_heading(self, _view: SearchView, title: str, subtitle: str) -> None:
        if self.stack.get_visible_child_name() != "search":
            return
        self.title.set_title(title)
        self.title.set_subtitle(subtitle)

    def _on_updates_heading(self, _view: UpdatesView, title: str, subtitle: str) -> None:
        if self.stack.get_visible_child_name() != "updates":
            return
        self.title.set_title(title)
        self.title.set_subtitle(subtitle)

    def _on_update_count(self, _view: UpdatesView, count: int) -> None:
        label = self.nav_counts.get("updates")
        if label is None:
            return
        label.set_label(str(count))
        label.set_visible(count > 0)
        if count > 0:
            self.update_button.set_label(f"Update ({count})")
            self.update_button.set_tooltip_text(f"Upgrade all installed packages ({count} pending)")
        else:
            self.update_button.set_label("Update system")
            self.update_button.set_tooltip_text("Upgrade all installed packages")

    def _on_heading_changed(self, _view: InstalledView, title: str, subtitle: str) -> None:
        if self.stack.get_visible_child_name() != "installed":
            return
        self.title.set_title(title)
        self.title.set_subtitle(subtitle)

    def _on_filter_changed(self, _view: InstalledView, mode: str) -> None:
        self.prefs.filter = mode
        self.prefs.save()
        self._syncing_nav = True
        if mode == "orphans":
            self.nav.select_row(self.rows["orphans"])
        elif mode == "apps":
            self.nav.select_row(self.rows["apps"])
        elif self.nav.get_selected_row() in (self.rows["orphans"], self.rows["apps"]):
            self.nav.select_row(self.rows["installed"])
        self._syncing_nav = False

    def _on_selection_changed(self, _view: InstalledView, has_selection: bool) -> None:
        self.remove_button.set_sensitive(has_selection)

    def _update_system(self, *_args: object) -> None:
        self.updates.update_system()

    def _refresh(self, *_args: object) -> None:
        page = self.stack.get_visible_child_name()
        if page == "updates":
            self.updates.refresh()
        elif page == "search":
            self.search.repeat()
        elif page == "tools":
            self.tools.refresh()
        elif page == "installed":
            self.installed.refresh()

    def _remove(self, *_args: object) -> None:
        if self._typing_focused():
            return
        if self.stack.get_visible_child_name() == "installed":
            self.installed.remove_selected()

    def _focus_search(self, *_args: object) -> None:
        if self.stack.get_visible_child_name() == "search":
            self.search.focus_search()
            return
        self._syncing_nav = True
        nav_id = {"orphans": "orphans", "apps": "apps"}.get(self.installed.get_filter(), "installed")
        self.nav.select_row(self.rows[nav_id])
        self._syncing_nav = False
        self.stack.set_visible_child_name("installed")
        self.refresh_button.set_visible(True)
        self.remove_button.set_visible(True)
        self.installed.focus_search()

    def _typing_focused(self) -> bool:
        widget = self.get_focus()
        while widget is not None:
            if isinstance(widget, (Gtk.Entry, Gtk.Text, Gtk.TextView, Gtk.SearchEntry)):
                return True
            widget = widget.get_parent()
        return False

    def _show_shortcuts(self, *_args: object) -> None:
        dialog = Adw.ShortcutsDialog()
        section = Adw.ShortcutsSection(title="Packages")
        section.add(Adw.ShortcutsItem(title="Update system", accelerator="<Control>u"))
        section.add(Adw.ShortcutsItem(title="Search", accelerator="<Control>f"))
        section.add(Adw.ShortcutsItem(title="Refresh", accelerator="F5"))
        section.add(Adw.ShortcutsItem(title="Remove selected package", accelerator="Delete"))
        section.add(Adw.ShortcutsItem(title="Keyboard shortcuts", accelerator="<Control>question"))
        section.add(Adw.ShortcutsItem(title="Quit", accelerator="<Control>q"))
        dialog.add(section)
        dialog.present(self)

    def _show_about(self, *_args: object) -> None:
        helper = self.helper or "none"
        dialog = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon="system-software-install",
            version=__version__,
            comments="A transparent graphical package manager for Arch Linux.",
            developers=["Lumina"],
        )
        if hasattr(dialog, "set_debug_info"):
            dialog.set_debug_info(f"AUR helper: {helper}")
        dialog.present(self)

    def show_toast(self, message: str) -> None:
        self.toast.add_toast(Adw.Toast(title=message, timeout=4))

    def _on_close(self, *_args: object) -> bool:
        self._save_prefs()
        return False

    def _save_prefs(self) -> None:
        width = self.get_width()
        height = self.get_height()
        if width >= 200 and height >= 200:
            self.prefs.width = width
            self.prefs.height = height
        position = self.installed.get_paned_position()
        if position >= 200:
            self.prefs.paned_position = position
        self.prefs.filter = self.installed.get_filter()
        self.prefs.save()

    def _load_css(self) -> None:
        path = Path(__file__).resolve().parent / "style.css"
        if not path.exists():
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(str(path))
        display = Gdk.Display.get_default()
        if display is None:
            return
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def install_app_icon() -> None:
    root = Path(__file__).resolve().parent / "icons"
    display = Gdk.Display.get_default()
    if display is not None and root.is_dir():
        theme = Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(str(root))
    install_user_icon()


def install_user_icon() -> None:
    source = Path(__file__).resolve().parent / "icons" / "hicolor"
    if not source.is_dir():
        return
    icon_root = Path.home() / ".local" / "share" / "icons" / "hicolor"
    for icon in source.glob("*/apps/com.github.lumina.png"):
        destination = icon_root / icon.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != icon.read_bytes():
            destination.write_bytes(icon.read_bytes())
    applications = Path.home() / ".local" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    installed = shutil.which("lumina")
    if installed:
        command = installed
    else:
        launcher = Path(__file__).resolve().parents[1] / "bin" / "lumina"
        command = f'"{launcher}"' if " " in str(launcher) else str(launcher)
    desktop = applications / "com.github.lumina.desktop"
    desktop.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Name=Lumina",
                "Comment=Transparent package manager for Arch Linux",
                f"Exec={command}",
                "Icon=com.github.lumina",
                "Terminal=false",
                "Type=Application",
                "Categories=System;PackageManager;",
                "Keywords=pacman;aur;packages;arch;",
                "StartupNotify=true",
                "StartupWMClass=com.github.lumina",
                "",
            ]
        ),
        encoding="utf-8",
    )
    for cache_tool in ("gtk4-update-icon-cache", "gtk-update-icon-cache"):
        if shutil.which(cache_tool):
            subprocess.run([cache_tool, "-f", "-t", str(icon_root)], check=False, capture_output=True)
            break
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=False, capture_output=True)
