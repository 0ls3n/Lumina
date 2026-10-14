from pathlib import Path

from lumina import gi_init

gi_init.ensure()

from gi.repository import Gdk, Gtk

_FALLBACK = "application-x-executable"
_PIXMAP_DIRS = (
    Path("/usr/share/pixmaps"),
    Path("/usr/share/icons/hicolor/scalable/apps"),
    Path("/usr/share/icons/hicolor/128x128/apps"),
    Path("/usr/share/icons/hicolor/64x64/apps"),
    Path("/usr/share/icons/hicolor/48x48/apps"),
)


def apply_app_icon(image: Gtk.Image, icon: str, size: int = 40) -> None:
    image.set_pixel_size(size)
    text = icon.strip()
    direct = Path(text)
    if direct.is_file():
        image.set_from_file(str(direct))
        return
    theme = _theme()
    for candidate in _names(text):
        if theme is not None and theme.has_icon(candidate):
            image.set_from_icon_name(candidate)
            return
    found = _icon_file(text)
    if found is not None:
        image.set_from_file(str(found))
        return
    image.set_from_icon_name(_FALLBACK)


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
