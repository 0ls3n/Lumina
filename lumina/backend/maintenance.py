import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lumina.backend.pacman import PacmanError, PreviewResult, run_query, validate_package_names
from lumina.backend.parser import parse_packages
from lumina.backend.updates import _privileged, _tools

CACHE_DIR = Path("/var/cache/pacman/pkg")


@dataclass(frozen=True)
class Orphan:
    name: str
    version: str


@dataclass(frozen=True)
class CacheReport:
    total_bytes: int
    unused_bytes: int
    file_count: int
    unused_count: int
    readable: bool


@dataclass(frozen=True)
class DiskReport:
    mount: str
    total_bytes: int
    free_bytes: int
    apps_bytes: int
    files_bytes: int | None
    cache_bytes: int
    files_on_disk: bool

    @property
    def used_bytes(self) -> int:
        return max(0, self.total_bytes - self.free_bytes)


@dataclass(frozen=True)
class MaintenanceSnapshot:
    orphans: tuple[Orphan, ...]
    cache: CacheReport
    paccache: bool
    disk: DiskReport


def parse_orphans(text: str) -> list[Orphan]:
    orphans: list[Orphan] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            orphans.append(Orphan(parts[0], parts[1]))
    return orphans


def cache_usage(files: list[tuple[str, int]], installed: list[tuple[str, str]]) -> tuple[int, int, int, int]:
    prefixes = tuple(f"{name}-{version}-" for name, version in installed)
    total = 0
    unused = 0
    unused_count = 0
    for name, size in files:
        total += size
        if not _is_installed_cache(name, prefixes):
            unused += size
            unused_count += 1
    return total, unused, len(files), unused_count


def disk_segments(report: DiskReport) -> list[tuple[str, int]]:
    files = report.files_bytes if report.files_on_disk and report.files_bytes is not None else 0
    apps = max(0, report.apps_bytes)
    cache = max(0, report.cache_bytes)
    used = report.used_bytes
    accounted = apps + files + cache
    if accounted > used and accounted > 0:
        scale = used / accounted
        apps = int(apps * scale)
        files = int(files * scale)
        cache = max(0, used - apps - files)
        other = 0
    else:
        other = max(0, used - accounted)
    return [
        ("apps", apps),
        ("files", files),
        ("cache", cache),
        ("other", other),
        ("free", max(0, report.free_bytes)),
    ]


def load_maintenance() -> MaintenanceSnapshot:
    orphans = tuple(parse_orphans(run_query(["-Qdt"], allow_empty=True)))
    installed = _installed_versions(run_query(["-Q"], allow_empty=True))
    cache = _read_cache(installed)
    disk = _read_disk(cache.total_bytes if cache.readable else 0)
    return MaintenanceSnapshot(
        orphans=orphans,
        cache=cache,
        paccache=shutil.which("paccache") is not None,
        disk=disk,
    )


def preview_orphan_removal(names: list[str]) -> PreviewResult:
    validate_package_names(names)
    text = run_query(["-Rsp", "--color", "never", *names], allow_empty=True)
    targets = [line.strip() for line in text.splitlines() if line.strip()]
    return PreviewResult(ok=True, targets=targets, message="")


def remove_orphans_command(names: list[str]) -> list[str]:
    validate_package_names(names)
    pkexec, pacman, stdbuf = _tools()
    return _privileged(
        pacman,
        ["--color", "never", "-Rns", "--noconfirm", *names],
        pkexec=pkexec,
        stdbuf=stdbuf,
    )


def clean_unused_cache_command() -> list[str]:
    pkexec, pacman, stdbuf = _tools()
    return _privileged(pacman, ["--color", "never", "-Sc", "--noconfirm"], pkexec=pkexec, stdbuf=stdbuf)


def clean_all_cache_command() -> list[str]:
    pkexec, pacman, stdbuf = _tools()
    return _privileged(pacman, ["--color", "never", "-Scc", "--noconfirm"], pkexec=pkexec, stdbuf=stdbuf)


def _installed_versions(text: str) -> list[tuple[str, str]]:
    installed: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            installed.append((parts[0], parts[1]))
    return installed


def _read_cache(installed: list[tuple[str, str]]) -> CacheReport:
    if not CACHE_DIR.is_dir() or not os.access(CACHE_DIR, os.R_OK):
        return CacheReport(0, 0, 0, 0, False)
    files: list[tuple[str, int]] = []
    try:
        for path in CACHE_DIR.iterdir():
            if not path.is_file():
                continue
            try:
                files.append((path.name, path.stat().st_size))
            except OSError:
                continue
    except OSError:
        return CacheReport(0, 0, 0, 0, False)
    total, unused, count, unused_count = cache_usage(files, installed)
    return CacheReport(total, unused, count, unused_count, True)


def _read_disk(cache_bytes: int) -> DiskReport:
    total, free = _filesystem_usage("/")
    home = Path.home()
    files_on_disk = _same_device("/", home)
    return DiskReport(
        mount="/",
        total_bytes=total,
        free_bytes=free,
        apps_bytes=_installed_apps_size(),
        files_bytes=_directory_size(home),
        cache_bytes=cache_bytes,
        files_on_disk=files_on_disk,
    )


def _filesystem_usage(path: str) -> tuple[int, int]:
    stats = os.statvfs(path)
    total = stats.f_blocks * stats.f_frsize
    free = stats.f_bavail * stats.f_frsize
    return total, max(0, free)


def _same_device(left: str | Path, right: str | Path) -> bool:
    try:
        return os.stat(left).st_dev == os.stat(right).st_dev
    except OSError:
        return False


def _installed_apps_size() -> int:
    packages = parse_packages(run_query(["-Qi"]))
    return sum(package.installed_size or 0 for package in packages)


def _directory_size(path: Path) -> int | None:
    du = shutil.which("du")
    if du is None or not path.is_dir():
        return None
    try:
        result = subprocess.run(
            [du, "-sb", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if not result.stdout.strip():
        return None
    try:
        return int(result.stdout.split()[0])
    except ValueError:
        return None


def _is_installed_cache(filename: str, prefixes: tuple[str, ...]) -> bool:
    base = filename[:-4] if filename.endswith(".sig") else filename
    return any(base.startswith(prefix) for prefix in prefixes)
