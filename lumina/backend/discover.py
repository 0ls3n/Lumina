import re
from dataclasses import dataclass

from lumina.backend.appicons import ensure_icon_cache
from lumina.backend.aur import detect_helper
from lumina.backend.pacman import PacmanError, parse_query_names, run_query
from lumina.backend.search import SearchResult, _run_search, parse_search_output

CatalogApp = tuple[str, str, str]

CATEGORIES: tuple[tuple[str, str, tuple[CatalogApp, ...]], ...] = (
    (
        "popular",
        "Popular",
        (
            ("firefox", "Firefox", "firefox"),
            ("vlc", "VLC", "vlc"),
            ("gimp", "GIMP", "gimp"),
            ("blender", "Blender", "blender"),
            ("obs-studio", "OBS Studio", "com.obsproject.Studio"),
            ("discord", "Discord", "discord"),
            ("steam", "Steam", "steam"),
            ("libreoffice-fresh", "LibreOffice", "libreoffice-writer"),
            ("code", "VS Code", "vscode"),
            ("krita", "Krita", "krita"),
            ("telegram-desktop", "Telegram", "org.telegram.desktop"),
            ("godot", "Godot", "godot"),
        ),
    ),
    (
        "web",
        "Web",
        (
            ("firefox", "Firefox", "firefox"),
            ("chromium", "Chromium", "chromium"),
            ("thunderbird", "Thunderbird", "thunderbird"),
        ),
    ),
    (
        "creative",
        "Creative",
        (
            ("gimp", "GIMP", "gimp"),
            ("krita", "Krita", "krita"),
            ("inkscape", "Inkscape", "inkscape"),
            ("blender", "Blender", "blender"),
            ("darktable", "Darktable", "darktable"),
            ("kdenlive", "Kdenlive", "kdenlive"),
            ("audacity", "Audacity", "audacity"),
            ("shotwell", "Shotwell", "shotwell"),
        ),
    ),
    (
        "games",
        "Games",
        (
            ("steam", "Steam", "steam"),
            ("lutris", "Lutris", "lutris"),
            ("godot", "Godot", "godot"),
            ("prismlauncher", "Prism Launcher", "org.prismlauncher.PrismLauncher"),
            ("retroarch", "RetroArch", "retroarch"),
            ("0ad", "0 A.D.", "0ad"),
            ("supertuxkart", "SuperTuxKart", "supertuxkart"),
            ("luanti", "Luanti", "luanti"),
        ),
    ),
    (
        "media",
        "Media",
        (
            ("vlc", "VLC", "vlc"),
            ("mpv", "mpv", "mpv"),
            ("strawberry", "Strawberry", "strawberry"),
            ("rhythmbox", "Rhythmbox", "rhythmbox"),
            ("kodi", "Kodi", "kodi"),
            ("handbrake", "HandBrake", "fr.handbrake.ghb"),
            ("calibre", "Calibre", "calibre"),
        ),
    ),
    (
        "chat",
        "Communication",
        (
            ("discord", "Discord", "discord"),
            ("telegram-desktop", "Telegram", "org.telegram.desktop"),
            ("signal-desktop", "Signal", "org.signal.Signal"),
            ("thunderbird", "Thunderbird", "thunderbird"),
        ),
    ),
    (
        "development",
        "Development",
        (
            ("code", "VS Code", "vscode"),
            ("neovim", "Neovim", "neovim"),
            ("git", "Git", "git"),
            ("docker", "Docker", "docker"),
            ("rust", "Rust", "rust"),
            ("go", "Go", "go"),
        ),
    ),
    (
        "utilities",
        "Utilities",
        (
            ("keepassxc", "KeePassXC", "keepassxc"),
            ("bitwarden", "Bitwarden", "bitwarden"),
            ("filezilla", "FileZilla", "filezilla"),
            ("qbittorrent", "qBittorrent", "qbittorrent"),
            ("transmission-gtk", "Transmission", "transmission"),
            ("calibre", "Calibre", "calibre"),
        ),
    ),
)

AUR_APPS: tuple[tuple[str, str, str, str], ...] = (
    ("spotify", "Spotify", "spotify-client", "media"),
    ("bottles", "Bottles", "com.usebottles.bottles", "games"),
)


@dataclass(frozen=True)
class DiscoverItem:
    result: SearchResult
    title: str
    icon: str


@dataclass(frozen=True)
class DiscoverSection:
    id: str
    title: str
    items: tuple[DiscoverItem, ...]


def catalog_names() -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for _id, _title, apps in CATEGORIES:
        for name, _label, _icon in apps:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def load_discover() -> list[DiscoverSection]:
    ensure_icon_cache()
    found = _lookup_official(catalog_names())
    aur = _lookup_aur()
    sections: list[DiscoverSection] = []
    for section_id, title, apps in CATEGORIES:
        items = [_item(name, label, icon, found) for name, label, icon in apps]
        items = [item for item in items if item is not None]
        if section_id == "media":
            items.extend(aur.get("media", []))
        elif section_id == "games":
            items.extend(aur.get("games", []))
        elif section_id == "popular":
            items.extend(aur.get("popular", []))
        if items:
            sections.append(DiscoverSection(section_id, title, tuple(items)))
    return sections


def _item(name: str, title: str, icon: str, found: dict[str, SearchResult]) -> DiscoverItem | None:
    result = found.get(name)
    if result is None:
        return None
    return DiscoverItem(result=result, title=title, icon=icon)


def _lookup_official(names: list[str]) -> dict[str, SearchResult]:
    if not names:
        return {}
    pattern = "^(" + "|".join(re.escape(name) for name in names) + ")$"
    parsed = parse_search_output(run_query(["-Ss", "--color", "never", pattern], allow_empty=True), "official")
    installed = parse_query_names(run_query(["-Qq"], allow_empty=True))
    wanted = set(names)
    found: dict[str, SearchResult] = {}
    for item in parsed:
        if item.name not in wanted or item.name in found:
            continue
        if item.name in installed and not item.installed:
            item = SearchResult(item.name, item.version, item.repo, item.description, True, item.source)
        found[item.name] = item
    return found


def _lookup_aur() -> dict[str, list[DiscoverItem]]:
    helper = detect_helper()
    if not helper:
        return {}
    grouped: dict[str, list[DiscoverItem]] = {}
    for name, title, icon, section in AUR_APPS:
        try:
            parsed = parse_search_output(_run_search([helper, "-Ssa", "--color", "never", name]), "aur")
        except PacmanError:
            continue
        match = next((item for item in parsed if item.name == name), None)
        if match is None:
            continue
        grouped.setdefault(section, []).append(DiscoverItem(result=match, title=title, icon=icon))
        if section != "popular":
            grouped.setdefault("popular", []).append(DiscoverItem(result=match, title=title, icon=icon))
    return grouped
