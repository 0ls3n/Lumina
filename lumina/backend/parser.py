import re
from datetime import datetime

from lumina.models.package import Package

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 ]*?)\s+:\s?(.*)$")
_SIZE_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)$")
_SIZE_UNITS = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
    "kB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
}
_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_size(value: str) -> int | None:
    text = value.strip()
    if not text or text == "None":
        return None
    match = _SIZE_RE.match(text)
    if not match:
        return None
    unit = _SIZE_UNITS.get(match.group(2))
    if unit is None:
        return None
    return int(float(match.group(1)) * unit)


def parse_pacman_date(value: str) -> datetime | None:
    parts = value.split()
    if len(parts) != 5:
        return None
    _weekday, month, day, clock, year = parts
    month_number = _MONTHS.get(month)
    if month_number is None:
        return None
    try:
        hour, minute, second = (int(piece) for piece in clock.split(":"))
        return datetime(int(year), month_number, int(day), hour, minute, second)
    except ValueError:
        return None


def parse_info_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    current_key: str | None = None
    for line in text.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
                current_key = None
            continue
        match = _FIELD_RE.match(line)
        if match:
            current_key = match.group(1).strip()
            current[current_key] = match.group(2)
            continue
        if current_key and (line.startswith(" ") or line.startswith("\t")):
            extra = line.strip()
            if extra:
                current[current_key] = f"{current[current_key]}\n{extra}"
    if current:
        blocks.append(current)
    return blocks


def _clean(value: str) -> str:
    text = value.strip()
    if text == "None":
        return ""
    return text


def _as_list(value: str) -> list[str]:
    text = value.strip()
    if not text or text == "None":
        return []
    return text.split()


def _as_lines(value: str) -> list[str]:
    lines = [line.strip() for line in value.splitlines() if line.strip() and line.strip() != "None"]
    return lines


def package_from_fields(fields: dict[str, str]) -> Package:
    reason = _clean(fields.get("Install Reason", ""))
    repo = _clean(fields.get("Repository", "")) or None
    return Package(
        name=_clean(fields.get("Name", "")),
        version=_clean(fields.get("Version", "")),
        description=_clean(fields.get("Description", "")),
        architecture=_clean(fields.get("Architecture", "")),
        url=_clean(fields.get("URL", "")),
        licenses=_as_list(fields.get("Licenses", "")),
        groups=_as_list(fields.get("Groups", "")),
        provides=_as_list(fields.get("Provides", "")),
        depends=_as_list(fields.get("Depends On", "")),
        optional_deps=_as_lines(fields.get("Optional Deps", "")),
        required_by=_as_list(fields.get("Required By", "")),
        optional_for=_as_list(fields.get("Optional For", "")),
        conflicts=_as_list(fields.get("Conflicts With", "")),
        replaces=_as_list(fields.get("Replaces", "")),
        installed_size=parse_size(fields.get("Installed Size", "")),
        packager=_clean(fields.get("Packager", "")),
        build_date=parse_pacman_date(fields.get("Build Date", "")),
        install_date=parse_pacman_date(fields.get("Install Date", "")),
        install_reason=reason,
        validated_by=_clean(fields.get("Validated By", "")),
        repo=repo,
        explicit=reason.lower().startswith("explicitly"),
    )


def parse_packages(text: str) -> list[Package]:
    packages: list[Package] = []
    for fields in parse_info_blocks(text):
        package = package_from_fields(fields)
        if package.name:
            packages.append(package)
    return packages
