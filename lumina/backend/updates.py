import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from lumina.backend.aur import detect_helper
from lumina.backend.pacman import PacmanError, PreviewResult, run_query, validate_package_names

_UPGRADE_RE = re.compile(r"^(\S+)\s+(\S+)\s+->\s+(\S+)\s*$")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class PendingUpdate:
    name: str
    old_version: str
    new_version: str
    source: str

    @property
    def label(self) -> str:
        origin = "AUR" if self.source == "aur" else "official"
        return f"{self.name}  {self.old_version} -> {self.new_version}  ({origin})"


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_upgrades(text: str, source: str) -> list[PendingUpdate]:
    updates: list[PendingUpdate] = []
    for line in strip_ansi(text).splitlines():
        match = _UPGRADE_RE.match(line.strip())
        if match:
            updates.append(
                PendingUpdate(
                    name=match.group(1),
                    old_version=match.group(2),
                    new_version=match.group(3),
                    source=source,
                )
            )
    return updates


def load_pending_updates() -> tuple[list[PendingUpdate], str]:
    official = parse_upgrades(run_query(["-Qu"], allow_empty=True), "official")
    warning = ""
    aur: list[PendingUpdate] = []
    helper = detect_helper()
    if helper:
        try:
            aur = parse_upgrades(_run_tool([helper, "-Qua"]), "aur")
        except PacmanError as exc:
            warning = f"Could not check AUR updates: {exc}"
    merged: dict[str, PendingUpdate] = {item.name: item for item in official}
    for item in aur:
        merged[item.name] = item
    updates = sorted(merged.values(), key=lambda item: item.name.casefold())
    return updates, warning


def preview_official_upgrades() -> PreviewResult:
    text = run_query(["-Sup", "--print-format", "%n %v"], allow_empty=True)
    targets = [line.strip() for line in text.splitlines() if line.strip()]
    return PreviewResult(ok=True, targets=targets, message="")


def system_update_command() -> list[str]:
    helper = detect_helper()
    helper_path = shutil.which(helper) if helper else None
    pkexec, pacman, stdbuf = _tools()
    if helper_path:
        argv = [helper_path, "-Syu", "--noconfirm", "--sudo", pkexec]
        if stdbuf:
            return [stdbuf, "-oL", "-eL", *argv]
        return argv
    return _privileged(pacman, ["--color", "never", "-Syu", "--noconfirm"], pkexec=pkexec, stdbuf=stdbuf)


def package_update_command(update: PendingUpdate) -> list[str]:
    validate_package_names([update.name])
    pkexec, pacman, stdbuf = _tools()
    if update.source == "aur":
        helper = detect_helper()
        helper_path = shutil.which(helper) if helper else None
        if not helper_path:
            raise PacmanError("No AUR helper is available to update this package.")
        argv = [helper_path, "-S", "--noconfirm", "--sudo", pkexec, update.name]
        if stdbuf:
            return [stdbuf, "-oL", "-eL", *argv]
        return argv
    return _privileged(
        pacman,
        ["--color", "never", "-S", "--noconfirm", update.name],
        pkexec=pkexec,
        stdbuf=stdbuf,
    )


def sync_command() -> list[str]:
    pkexec, pacman, stdbuf = _tools()
    return _privileged(pacman, ["--color", "never", "-Sy", "--noconfirm"], pkexec=pkexec, stdbuf=stdbuf)


def _tools() -> tuple[str, str, str | None]:
    pkexec = shutil.which("pkexec")
    pacman = shutil.which("pacman")
    if not pkexec:
        raise PacmanError("pkexec was not found. Install polkit to change packages.")
    if not pacman:
        raise PacmanError("pacman was not found.")
    return pkexec, pacman, shutil.which("stdbuf")


def _privileged(pacman: str, args: list[str], *, pkexec: str, stdbuf: str | None) -> list[str]:
    pacman_cmd = [pacman, *args]
    if stdbuf:
        return [pkexec, stdbuf, "-oL", "-eL", *pacman_cmd]
    return [pkexec, *pacman_cmd]


def _run_tool(argv: list[str]) -> str:
    path = shutil.which(argv[0])
    if not path:
        raise PacmanError(f"{argv[0]} was not found.")
    env = os.environ.copy()
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            [path, *argv[1:]],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        raise PacmanError(str(exc)) from exc
    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or result.stdout.strip() or f"exited with status {result.returncode}"
        raise PacmanError(detail)
    if result.returncode == 1 and "error:" in result.stderr.lower():
        raise PacmanError(result.stderr.strip())
    return result.stdout
