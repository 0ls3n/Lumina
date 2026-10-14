import json
from dataclasses import asdict, dataclass
from pathlib import Path

FILTERS = ("apps", "all", "explicit", "official", "foreign", "orphans")


@dataclass
class Preferences:
    width: int = 1100
    height: int = 720
    filter: str = "apps"
    paned_position: int = 620

    @property
    def path(self) -> Path:
        return Path.home() / ".config" / "lumina" / "config.json"

    @classmethod
    def load(cls) -> "Preferences":
        prefs = cls()
        try:
            data = json.loads(prefs.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return prefs
        if not isinstance(data, dict):
            return prefs
        width = _positive_int(data.get("width"), prefs.width)
        height = _positive_int(data.get("height"), prefs.height)
        position = _positive_int(data.get("paned_position"), prefs.paned_position)
        selected = data.get("filter", prefs.filter)
        if not isinstance(selected, str) or selected not in FILTERS:
            selected = prefs.filter
        return cls(width=width, height=height, filter=selected, paned_position=position)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = asdict(self)
            self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError:
            return


def _positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return fallback
    if value < 200:
        return fallback
    return value
