import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from lumina.backend.apps import discover_applications
from lumina.backend.parser import parse_packages
from lumina.models.package import Origin, Package

_NAME_RE = re.compile(r"^[A-Za-z0-9@._+][A-Za-z0-9@._+-]*$")

CRITICAL_PACKAGES = frozenset(
    {
        "base",
        "bash",
        "filesystem",
        "glibc",
        "linux",
        "pacman",
        "shadow",
        "sudo",
        "systemd",
    }
)


class PacmanError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreviewResult:
    ok: bool
    targets: list[str]
    message: str


def validate_package_names(names: list[str]) -> None:
    if not names:
        raise PacmanError("No package selected.")
    for name in names:
        if not _NAME_RE.match(name):
            raise PacmanError(f"Invalid package name: {name}")


def parse_query_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            names.add(stripped.split()[0])
    return names


def parse_sync_list(text: str) -> dict[str, str]:
    repos: dict[str, str] = {}
    installed: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        repo, name = parts[0], parts[1]
        if parts[-1] == "[installed]":
            installed[name] = repo
        elif name not in repos:
            repos[name] = repo
    repos.update(installed)
    return repos


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    return env


def run_query(args: list[str], *, allow_empty: bool = False) -> str:
    pacman = shutil.which("pacman")
    if not pacman:
        raise PacmanError("pacman was not found. Lumina only works on Arch Linux.")
    try:
        result = subprocess.run(
            [pacman, *args],
            capture_output=True,
            text=True,
            check=False,
            env=_command_env(),
        )
    except OSError as exc:
        raise PacmanError(str(exc)) from exc
    if result.returncode == 0:
        return result.stdout
    stderr = result.stderr.strip()
    if (
        allow_empty
        and result.returncode == 1
        and not result.stdout.strip()
        and "error:" not in stderr.lower()
    ):
        return ""
    detail = stderr or result.stdout.strip() or f"pacman exited with status {result.returncode}"
    raise PacmanError(detail)


def classify_package(
    package: Package,
    *,
    explicit: set[str],
    foreign: set[str],
    orphans: set[str],
    repos: dict[str, str],
) -> None:
    package.explicit = package.name in explicit
    package.orphan = package.name in orphans
    if package.name in foreign:
        package.origin = Origin.FOREIGN
        package.repo = None
    elif package.name in repos:
        package.origin = Origin.OFFICIAL
        package.repo = repos[package.name]
    else:
        package.origin = Origin.LOCAL
        package.repo = None


def load_installed_packages() -> list[Package]:
    info = run_query(["-Qi"])
    explicit = parse_query_names(run_query(["-Qeq"], allow_empty=True))
    foreign = parse_query_names(run_query(["-Qmq"], allow_empty=True))
    orphans = parse_query_names(run_query(["-Qdtq"], allow_empty=True))
    repos = parse_sync_list(run_query(["-Sl"], allow_empty=True))
    apps = discover_applications()
    packages = parse_packages(info)
    for package in packages:
        classify_package(
            package,
            explicit=explicit,
            foreign=foreign,
            orphans=orphans,
            repos=repos,
        )
        app = apps.get(package.name)
        if app is not None:
            package.app_name = app.name
            package.app_icon = app.icon
    packages.sort(key=lambda package: package.name.casefold())
    return packages


def build_remove_command(
    names: list[str],
    *,
    recursive: bool,
    pkexec: str = "/usr/bin/pkexec",
    pacman: str = "/usr/bin/pacman",
    stdbuf: str | None = None,
) -> list[str]:
    validate_package_names(names)
    flag = "-Rs" if recursive else "-R"
    pacman_cmd = [pacman, "--color", "never", flag, "--noconfirm", *names]
    if stdbuf:
        return [pkexec, stdbuf, "-oL", "-eL", *pacman_cmd]
    return [pkexec, *pacman_cmd]


def remove_command(names: list[str], *, recursive: bool) -> list[str]:
    pkexec = shutil.which("pkexec")
    pacman = shutil.which("pacman")
    if not pkexec:
        raise PacmanError("pkexec was not found. Install polkit to change packages.")
    if not pacman:
        raise PacmanError("pacman was not found.")
    return build_remove_command(
        names,
        recursive=recursive,
        pkexec=pkexec,
        pacman=pacman,
        stdbuf=shutil.which("stdbuf"),
    )


def preview_remove(names: list[str], *, recursive: bool) -> PreviewResult:
    validate_package_names(names)
    pacman = shutil.which("pacman")
    if not pacman:
        raise PacmanError("pacman was not found.")
    flag = "-Rsp" if recursive else "-Rp"
    try:
        result = subprocess.run(
            [pacman, "--color", "never", flag, *names],
            capture_output=True,
            text=True,
            check=False,
            env=_command_env(),
        )
    except OSError as exc:
        raise PacmanError(str(exc)) from exc
    targets = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"pacman exited with status {result.returncode}"
        return PreviewResult(ok=False, targets=targets, message=message)
    return PreviewResult(ok=True, targets=targets, message="")
