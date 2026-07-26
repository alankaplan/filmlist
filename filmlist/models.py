"""Data models for the film-festival database."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# The major international film festivals we track. Keeping this as a canonical
# list lets us validate input and drive the grouping in the generated page.
FESTIVALS = [
    "Cannes",
    "Venice",
    "Berlin",
    "Sundance",
    "Toronto",
    "Locarno",
    "San Sebastian",
    "Telluride",
]


@dataclass
class Film:
    """A single film screened at (or awarded by) a festival."""

    title: str
    year: int
    festival: str
    director: str = ""
    country: str = ""
    section: str = ""       # e.g. "Competition", "Un Certain Regard"
    award: str = ""         # e.g. "Palme d'Or", "Golden Lion"
    synopsis: str = ""
    id: Optional[int] = None

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.festival = self.festival.strip()
        if not self.title:
            raise ValueError("Film title must not be empty")
        if self.festival not in FESTIVALS:
            raise ValueError(
                f"Unknown festival {self.festival!r}. "
                f"Expected one of: {', '.join(FESTIVALS)}"
            )
        if not (1888 <= int(self.year) <= 2100):
            raise ValueError(f"Implausible year: {self.year}")
        self.year = int(self.year)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("id", None)
        return d
