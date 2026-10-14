from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopApp:
    name: str
    icon: str = ""


def discover_applications(
    local_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, DesktopApp]:
    root = local_root or Path("/var/lib/pacman/local")
    prefix = install_root or Path("/")
    if not root.is_dir():
        return {}
    found: dict[str, list[DesktopApp]] = {}
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        desktop_paths = _desktop_paths(entry / "files")
        if not desktop_paths:
            continue
        package = _read_local_name(entry)
        if not package:
            continue
        for relative in desktop_paths:
            app = read_desktop_app(prefix / relative)
            if app is not None:
                found.setdefault(package, []).append(app)
    return {package: pick_desktop_app(package, apps) for package, apps in found.items()}


def launchable_name(path: Path) -> str | None:
    app = read_desktop_app(path)
    if app is None:
        return None
    return app.name


def read_desktop_app(path: Path) -> DesktopApp | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    name = ""
    icon = ""
    entry_type = ""
    nodisplay = False
    hidden = False
    in_entry = False
    saw_entry = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if saw_entry:
                break
            in_entry = stripped == "[Desktop Entry]"
            saw_entry = in_entry
            continue
        if not in_entry or not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        raw = value.strip().strip('"').strip("'")
        lowered = raw.lower()
        if key == "Name" and raw and not name:
            name = raw
        elif key == "Icon" and raw and not icon:
            icon = raw
        elif key == "Type":
            entry_type = lowered
        elif key == "NoDisplay" and lowered == "true":
            nodisplay = True
        elif key == "Hidden" and lowered == "true":
            hidden = True
    if nodisplay or hidden or not name:
        return None
    if entry_type and entry_type != "application":
        return None
    return DesktopApp(name=name, icon=icon)


def pick_desktop_app(package: str, apps: list[DesktopApp]) -> DesktopApp:
    chosen = pick_app_name(package, [app.name for app in apps])
    for app in apps:
        if app.name == chosen:
            return app
    return apps[0]


def pick_app_name(package: str, names: list[str]) -> str:
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    folded = package.casefold().replace("-", " ")
    exact = [name for name in unique if name.casefold() == folded]
    if exact:
        return exact[0]
    contained = [name for name in unique if folded in name.casefold() or name.casefold() in folded]
    if contained:
        return min(contained, key=len)
    return min(unique, key=len)


def _desktop_paths(path: Path) -> list[str]:
    if not path.is_file():
        return []
    matches: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                relative = line.strip().lstrip("/")
                if relative.endswith(".desktop") and "/share/applications/" in f"/{relative}":
                    matches.append(relative)
    except OSError:
        return []
    return matches


def _read_local_name(entry: Path) -> str | None:
    try:
        lines = (entry / "desc").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for index, line in enumerate(lines):
        if line.strip() == "%NAME%" and index + 1 < len(lines):
            name = lines[index + 1].strip()
            return name or None
    return None
