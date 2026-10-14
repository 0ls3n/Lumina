import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from lumina.backend.appicons import ensure_icon_cache
from lumina.backend.aur import detect_helper
from lumina.backend.pacman import PacmanError, PreviewResult, parse_query_names, run_query, validate_package_names
from lumina.backend.updates import PendingUpdate, package_update_command, strip_ansi

_HEADER_RE = re.compile(
    r"^(?P<repo>[A-Za-z0-9][A-Za-z0-9+._-]*)/(?P<name>[A-Za-z0-9@._+-]+)\s+(?P<version>\S+)(?P<rest>.*)$"
)
_QUERY_RE = re.compile(r"^[A-Za-z0-9@._+\- ]+$")
_RESULT_LIMIT = 60


@dataclass(frozen=True)
class SearchResult:
    name: str
    version: str
    repo: str
    description: str
    installed: bool
    source: str


def clean_query(query: str) -> str:
    text = " ".join(query.split())
    if not text:
        raise PacmanError("Enter a package name to search.")
    if text.startswith("-") or not _QUERY_RE.match(text):
        raise PacmanError("Search query contains unsupported characters.")
    if len(text) > 80:
        raise PacmanError("Search query is too long.")
    return text


def parse_search_output(text: str, source: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    current: dict[str, str] | None = None

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        item_source = "aur" if current["repo"] == "aur" else source
        results.append(
            SearchResult(
                name=current["name"],
                version=current["version"],
                repo=current["repo"],
                description=current["description"].strip(),
                installed=current["installed"] == "1",
                source=item_source,
            )
        )
        current = None

    for raw in strip_ansi(text).splitlines():
        if not raw.strip():
            continue
        if raw.startswith((" ", "\t")):
            if current is not None and len(current["description"]) < 400:
                current["description"] = f"{current['description']} {raw.strip()}".strip()
            continue
        finish()
        match = _HEADER_RE.match(raw.strip())
        if not match:
            continue
        current = {
            "repo": match.group("repo"),
            "name": match.group("name"),
            "version": match.group("version"),
            "description": "",
            "installed": "1" if "[installed]" in match.group("rest") else "0",
        }
    finish()
    return results


def search_packages(query: str, *, scope: str = "both") -> tuple[list[SearchResult], str]:
    ensure_icon_cache()
    cleaned = clean_query(query)
    warning = ""
    official: list[SearchResult] = []
    aur: list[SearchResult] = []
    if scope in ("both", "official"):
        official = parse_search_output(
            run_query(["-Ss", "--color", "never", re.escape(cleaned)], allow_empty=True),
            "official",
        )
    if scope in ("both", "aur"):
        helper = detect_helper()
        if helper is None:
            if scope == "aur":
                warning = "No AUR helper found. Install yay or paru to search the AUR."
        else:
            try:
                aur = parse_search_output(
                    _run_search([helper, "-Ssa", "--color", "never", cleaned]),
                    "aur",
                )
            except PacmanError as exc:
                warning = f"AUR search failed: {exc}"
    installed = parse_query_names(run_query(["-Qq"], allow_empty=True))
    merged: list[SearchResult] = []
    seen: set[str] = set()
    for item in [*official[:_RESULT_LIMIT], *aur[:_RESULT_LIMIT]]:
        if item.name in seen:
            continue
        seen.add(item.name)
        if item.installed or item.name in installed:
            item = SearchResult(
                item.name,
                item.version,
                item.repo,
                item.description,
                True,
                item.source,
            )
        merged.append(item)
    needle = cleaned.casefold()
    merged.sort(key=lambda item: _rank(item, needle))
    note = warning
    if len(official) > _RESULT_LIMIT or len(aur) > _RESULT_LIMIT:
        extra = "Showing the first matches. Narrow the search for more."
        note = f"{note} {extra}".strip()
    return merged, note


def install_command(name: str, source: str) -> list[str]:
    validate_package_names([name])
    if source not in ("official", "aur"):
        raise PacmanError(f"Unknown package source: {source}")
    return package_update_command(PendingUpdate(name, "", "", source))


def preview_install(name: str) -> PreviewResult:
    validate_package_names([name])
    text = run_query(["-Sp", "--color", "never", name], allow_empty=True)
    targets = [line.strip() for line in text.splitlines() if line.strip()]
    return PreviewResult(ok=True, targets=targets or [name], message="")


def _rank(item: SearchResult, needle: str) -> tuple[int, int, int, str]:
    name = item.name.casefold()
    exact = 0 if name == needle else 1
    prefix = 0 if name.startswith(needle) else 1
    official = 0 if item.source == "official" else 1
    return (exact, prefix, official, name)


def _run_search(argv: list[str]) -> str:
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
            timeout=25,
        )
    except subprocess.TimeoutExpired as exc:
        raise PacmanError(f"{argv[0]} search timed out.") from exc
    except OSError as exc:
        raise PacmanError(str(exc)) from exc
    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or result.stdout.strip() or f"exited with status {result.returncode}"
        raise PacmanError(detail)
    if result.returncode == 1 and "error:" in result.stderr.lower():
        raise PacmanError(result.stderr.strip())
    return result.stdout
