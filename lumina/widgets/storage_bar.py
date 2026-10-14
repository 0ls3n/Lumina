from lumina import gi_init

gi_init.ensure()

import gi

gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Graphene, Gsk, Gtk


class StorageBar(Gtk.Widget):
    __gtype_name__ = "LuminaStorageBar"

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_size_request(-1, 22)
        self.add_css_class("storage-bar")
        self._children: list[Gtk.Widget] = []
        self._amounts: list[int] = []

    def set_segments(self, segments: list[tuple[str, int]]) -> None:
        for child in self._children:
            child.unparent()
        self._children.clear()
        self._amounts.clear()
        for name, amount in segments:
            if amount <= 0:
                continue
            segment = Gtk.Box()
            segment.add_css_class("storage-segment")
            segment.add_css_class(f"storage-{name}")
            segment.set_parent(self)
            self._children.append(segment)
            self._amounts.append(amount)
        self.queue_allocate()

    def do_measure(self, orientation: Gtk.Orientation, _for_size: int) -> tuple[int, int, int, int]:
        if orientation == Gtk.Orientation.VERTICAL:
            return (22, 22, -1, -1)
        return (120, 240, -1, -1)

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        total = sum(self._amounts) or 1
        used = 0
        for index, (child, amount) in enumerate(zip(self._children, self._amounts)):
            if index == len(self._children) - 1:
                part = max(0, width - used)
            else:
                part = max(0, int(width * amount / total))
            point = Graphene.Point()
            point.init(float(used), 0)
            transform = Gsk.Transform().translate(point)
            child.allocate(part, height, baseline, transform)
            used += part

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        child = self.get_first_child()
        while child is not None:
            self.snapshot_child(child, snapshot)
            child = child.get_next_sibling()

    def do_unroot(self) -> None:
        for child in self._children:
            child.unparent()
        self._children.clear()
        Gtk.Widget.do_unroot(self)
