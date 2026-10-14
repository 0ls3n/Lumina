from pathlib import Path

from lumina import gi_init

gi_init.ensure()

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gtk

from lumina.backend.appicons import cached_icon

_FALLBACK = "application-x-executable"
_PIXMAP_DIRS = (
    Path("/usr/share/pixmaps"),
    Path("/usr/share/icons/hicolor/scalable/apps"),
    Path("/usr/share/icons/hicolor/128x128/apps"),
    Path("/usr/share/icons/hicolor/64x64/apps"),
    Path("/usr/share/icons/hicolor/48x48/apps"),
)


def apply_app_icon(image: Gtk.Image, icon: str, size: int = 40, package: str = "") -> None:
    image.set_pixel_size(size)
    text = icon.strip()
    direct = Path(text)
    if direct.is_file():
        _set_from_path(image, direct, size)
        return
    theme = _theme()
    for candidate in _names(text):
        if theme is not None and theme.has_icon(candidate):
            image.set_from_icon_name(candidate)
            return
    found = _icon_file(text) or cached_icon(text, package)
    if found is not None:
        _set_from_path(image, found, size)
        return
    image.set_from_icon_name(_FALLBACK)


def _set_from_path(image: Gtk.Image, path: Path, size: int) -> None:
    if path.suffix.lower() == ".jxl":
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), size, size)
        image.set_from_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
        return
    image.set_from_file(str(path))


def _icon_file(icon: str) -> Path | None:
    for candidate in _names(icon):
        if "/" in candidate:
            continue
        for directory in _PIXMAP_DIRS:
            for suffix in ("", ".png", ".svg", ".xpm"):
                guess = directory / f"{candidate}{suffix}"
                if guess.is_file():
                    return guess
    return None


def _names(icon: str) -> list[str]:
    text = icon.strip()
    if not text:
        return []
    names = [text]
    suffix = Path(text).suffix.lower()
    if suffix in {".png", ".svg", ".xpm"}:
        names.append(Path(text).stem)
    return names


def _theme() -> Gtk.IconTheme | None:
    display = Gdk.Display.get_default()
    if display is None:
        return None
    return Gtk.IconTheme.get_for_display(display)
