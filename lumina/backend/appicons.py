import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache" / "lumina" / "appstream-icons"
INDEX_PATH = CACHE / "index.json"
SYSTEM_ICONS = Path("/usr/share/swcatalog/icons")

_index: dict[str, dict[str, str]] | None = None


def ensure_icon_cache() -> None:
    global _index
    if INDEX_PATH.is_file() and _has_icons(CACHE):
        _index = _read_index(INDEX_PATH)
        return
    if _has_icons(SYSTEM_ICONS):
        _index = _build_index(SYSTEM_ICONS)
        _write_index(_index)
        return
    try:
        archive = _download_package()
    except (OSError, subprocess.SubprocessError, ValueError):
        _index = {"by_icon": {}, "by_package": {}}
        return
    icons = CACHE / "icons"
    if icons.exists():
        shutil.rmtree(icons)
    icons.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bsdtar", "-xf", str(archive), "-C", str(icons), "usr/share/swcatalog/icons"],
        check=False,
        capture_output=True,
    )
    archive.unlink(missing_ok=True)
    _index = _build_index(icons)
    _write_index(_index)


def cached_icon(icon: str = "", package: str = "") -> Path | None:
    index = _load_index()
    for key in (icon, package):
        if not key:
            continue
        path = index["by_icon"].get(key) or index["by_package"].get(key)
        if path and Path(path).is_file():
            return Path(path)
    return None


def build_index(root: Path) -> dict[str, dict[str, str]]:
    return _build_index(root)


def _build_index(root: Path) -> dict[str, dict[str, str]]:
    by_icon: dict[str, str] = {}
    by_package: dict[str, str] = {}
    if not root.is_dir():
        return {"by_icon": by_icon, "by_package": by_package}
    for path in root.rglob("128x128/*.jxl"):
        package, icon = _split_name(path.stem)
        if not package or not icon:
            continue
        location = str(path)
        if icon not in by_icon or icon == package:
            by_icon[icon] = location
        if package not in by_package or icon == package:
            by_package[package] = location
    return {"by_icon": by_icon, "by_package": by_package}


def _split_name(stem: str) -> tuple[str, str]:
    if "_" not in stem:
        return "", ""
    package, icon = stem.split("_", 1)
    return package, icon


def _has_icons(root: Path) -> bool:
    return root.is_dir() and any(root.rglob("128x128/*.jxl"))


def _download_package() -> Path:
    url = _package_url()
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / "archlinux-appstream-data.pkg.tar.zst"
    request = urllib.request.Request(url, headers={"User-Agent": "Lumina"})
    with urllib.request.urlopen(request, timeout=90) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return dest


def _package_url() -> str:
    env = os.environ.copy()
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    result = subprocess.run(
        ["pacman", "-Sddp", "archlinux-appstream-data"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    for line in reversed(result.stdout.splitlines()):
        if line.startswith("https://") and line.endswith(".pkg.tar.zst"):
            return line.strip()
    raise ValueError("Could not find the app icon package.")


def _read_index(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"by_icon": {}, "by_package": {}}
    if not isinstance(data, dict):
        return {"by_icon": {}, "by_package": {}}
    return {
        "by_icon": dict(data.get("by_icon", {})),
        "by_package": dict(data.get("by_package", {})),
    }


def _write_index(index: dict[str, dict[str, str]]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index), encoding="utf-8")


def _load_index() -> dict[str, dict[str, str]]:
    global _index
    if _index is None:
        _index = _read_index(INDEX_PATH) if INDEX_PATH.is_file() else {"by_icon": {}, "by_package": {}}
    return _index
