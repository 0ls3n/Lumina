from lumina import gi_init

gi_init.ensure()

from gi.repository import Gtk

FILTERS = (
    ("apps", "Apps"),
    ("all", "All installed"),
    ("explicit", "Explicit"),
    ("official", "Official repos"),
    ("foreign", "AUR / foreign"),
    ("orphans", "Orphans"),
)


class FilterBar(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(spacing=8)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self._handler: object | None = None
        self.search = Gtk.SearchEntry(placeholder_text="Search name or description", hexpand=True)
        labels = Gtk.StringList.new([label for _mode, label in FILTERS])
        self.dropdown = Gtk.DropDown(model=labels)
        self.dropdown.set_size_request(180, -1)
        self.append(self.search)
        self.append(self.dropdown)

    def connect_search(self, callback) -> None:
        self.search.connect("search-changed", lambda entry: callback(entry.get_text()))

    def connect_filter(self, callback) -> None:
        self._handler = self.dropdown.connect("notify::selected", lambda *_args: callback(self.mode))

    @property
    def mode(self) -> str:
        index = self.dropdown.get_selected()
        if index < 0 or index >= len(FILTERS):
            return "all"
        return FILTERS[index][0]

    def set_mode(self, mode: str) -> None:
        for index, (value, _label) in enumerate(FILTERS):
            if value == mode:
                if self._handler is not None:
                    self.dropdown.handler_block(self._handler)
                self.dropdown.set_selected(index)
                if self._handler is not None:
                    self.dropdown.handler_unblock(self._handler)
                return

    def focus_search(self) -> None:
        self.search.grab_focus()
        self.search.select_region(0, -1)
