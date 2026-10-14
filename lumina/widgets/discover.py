from collections.abc import Callable

from lumina import gi_init

gi_init.ensure()

from gi.repository import Gtk, Pango

from lumina.backend.discover import DiscoverSection
from lumina.backend.search import SearchResult
from lumina.widgets.icons import apply_app_icon


class DiscoverBrowser(Gtk.ScrolledWindow):
    def __init__(self, on_install: Callable[[SearchResult], None]) -> None:
        super().__init__(vexpand=True)
        self._on_install = on_install
        self._sections: list[DiscoverSection] = []
        self._filter = "all"
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        root.set_margin_top(4)
        root.set_margin_bottom(16)
        intro = Gtk.Label(label="Discover apps to install", xalign=0)
        intro.add_css_class("title-2")
        root.append(intro)
        self.chip_box = Gtk.Box(spacing=6)
        chip_scroll = Gtk.ScrolledWindow(child=self.chip_box, vexpand=False)
        chip_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        chip_scroll.set_propagate_natural_height(True)
        root.append(chip_scroll)
        self.sections = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.append(self.sections)
        self.set_child(root)

    def set_sections(self, sections: list[DiscoverSection]) -> None:
        self._sections = sections
        self._build_chips()
        self._build_sections()

    def _build_chips(self) -> None:
        while child := self.chip_box.get_first_child():
            self.chip_box.remove(child)
        group: Gtk.ToggleButton | None = None
        for section_id, title in [("all", "All"), *[(section.id, section.title) for section in self._sections]]:
            button = Gtk.ToggleButton(label=title)
            button.add_css_class("pill")
            if group is None:
                group = button
                button.set_active(True)
            else:
                button.set_group(group)
            button.connect("toggled", self._on_chip, section_id)
            self.chip_box.append(button)
        self._filter = "all"

    def _on_chip(self, button: Gtk.ToggleButton, section_id: str) -> None:
        if not button.get_active():
            return
        self._filter = section_id
        self._build_sections()

    def _build_sections(self) -> None:
        while child := self.sections.get_first_child():
            self.sections.remove(child)
        for section in self._sections:
            if self._filter not in ("all", section.id):
                continue
            self.sections.append(self._section(section))

    def _section(self, section: DiscoverSection) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        heading = Gtk.Label(label=section.title, xalign=0)
        heading.add_css_class("heading")
        box.append(heading)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True)
        flow.set_min_children_per_line(2)
        flow.set_max_children_per_line(4)
        flow.set_column_spacing(8)
        flow.set_row_spacing(8)
        for item in section.items:
            flow.append(self._card(item.result, item.title, item.icon))
        box.append(flow)
        return box

    def _card(self, result: SearchResult, title: str, icon: str) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("discover-card")
        card.set_size_request(156, -1)
        image = Gtk.Image(halign=Gtk.Align.START)
        apply_app_icon(image, icon or result.name, 48, result.name)
        name = Gtk.Label(label=title, xalign=0)
        name.add_css_class("heading")
        name.set_ellipsize(Pango.EllipsizeMode.END)
        description = Gtk.Label(label=result.description or result.repo, xalign=0, wrap=True)
        description.add_css_class("caption")
        description.add_css_class("dim-label")
        description.set_lines(2)
        description.set_ellipsize(Pango.EllipsizeMode.END)
        description.set_max_width_chars(18)
        if result.installed:
            action = Gtk.Label(label="Installed", xalign=0)
            action.add_css_class("caption")
            action.add_css_class("dim-label")
        else:
            action = Gtk.Button(label="Install")
            action.add_css_class("suggested-action")
            action.add_css_class("pill")
            action.set_halign(Gtk.Align.START)
            action.connect("clicked", lambda *_args, item=result: self._on_install(item))
        card.append(image)
        card.append(name)
        card.append(description)
        card.append(action)
        return card
