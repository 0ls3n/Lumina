from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Origin(Enum):
    OFFICIAL = "official"
    AUR = "aur"
    FOREIGN = "foreign"
    LOCAL = "local"


@dataclass
class Package:
    name: str
    version: str
    description: str = ""
    architecture: str = ""
    url: str = ""
    licenses: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    optional_deps: list[str] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)
    optional_for: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    replaces: list[str] = field(default_factory=list)
    installed_size: int | None = None
    packager: str = ""
    build_date: datetime | None = None
    install_date: datetime | None = None
    install_reason: str = ""
    validated_by: str = ""
    repo: str | None = None
    origin: Origin = Origin.LOCAL
    explicit: bool = False
    orphan: bool = False
    app_name: str = ""
    app_icon: str = ""

    @property
    def badge(self) -> str:
        if self.origin is Origin.OFFICIAL and self.repo:
            return self.repo
        if self.origin is Origin.AUR:
            return "AUR"
        if self.origin is Origin.FOREIGN:
            return "foreign"
        return "local"

    @property
    def badge_style(self) -> str:
        if self.origin is Origin.OFFICIAL:
            return "official"
        if self.origin in (Origin.FOREIGN, Origin.AUR):
            return "foreign"
        return "local"

    @property
    def reason_label(self) -> str:
        if self.install_reason:
            return self.install_reason
        if self.explicit:
            return "Explicitly installed"
        return "Installed as a dependency for another package"
