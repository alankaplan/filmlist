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
    "SXSW",
    "Toronto",
    "Locarno",
    "San Sebastian",
    "Telluride",
    "Oscars",
]


@dataclass
class Film:
    """A single film screened at (or awarded by) a festival."""

    title: str
    year: int
    festival: str
    director: str = ""
    country: str = ""
    genre: str = ""         # comma-separated, e.g. "Drama, Thriller"
    section: str = ""       # e.g. "Competition", "Un Certain Regard"
    award: str = ""         # e.g. "Palme d'Or", "Golden Lion"
    synopsis: str = ""
    tags: str = ""          # comma-separated, e.g. "OK for 12, Cannes pick"
    rt_score: str = ""      # Rotten Tomatoes Tomatometer, e.g. "85%"
    id: Optional[int] = None

    @property
    def genres(self) -> list[str]:
        """The genre string split into individual, trimmed labels."""
        return [g.strip() for g in self.genre.split(",") if g.strip()]

    @property
    def rt_percent(self) -> Optional[int]:
        """The Tomatometer as an integer percentage, or None if unknown."""
        digits = "".join(c for c in self.rt_score if c.isdigit())
        return int(digits) if digits else None

    @property
    def tag_list(self) -> list[str]:
        """The tag string split into individual, trimmed labels."""
        return [t.strip() for t in self.tags.split(",") if t.strip()]

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
