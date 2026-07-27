"""Automatic tagging for films.

The age-appropriateness tags are a transparent heuristic derived from a
film's genres — festival films rarely carry a machine-readable content
rating, so genre is the signal we always have. Every film gets exactly one
"floor" age tag (plus the implied younger-friendly one), so nothing is left
untagged:

    genres suitable for young children   -> "OK for 5", "OK for 12"
    generally suitable for tweens         -> "OK for 12"
    mature themes / unknown               -> "16+"
    explicitly adult                      -> "18+"

This is a rough automated estimate, not a substitute for an official rating.
"""

from __future__ import annotations

AGE_5 = "OK for 5"
AGE_12 = "OK for 12"
AGE_16 = "16+"
AGE_18 = "18+"

# All age tags, youngest-friendly first (used to build filter options).
AGE_TAGS = [AGE_5, AGE_12, AGE_16, AGE_18]

# Genre keywords, matched as case-insensitive substrings so "war film" hits
# "war" and "psychological thriller" hits "thriller".
_ADULT = (
    "porn", "erotic", "hardcore", "exploitation", "slasher", "splatter",
    "giallo", "snuff",
)
_MATURE = (
    "horror", "thriller", "crime", "war", "noir", "gangster", "slasher",
    "action", "western", "martial arts", "disaster", "zombie", "vampire",
)
_KID = (
    "animation", "animated", "family", "children", "stop motion",
    "computer animation",
)
_TWEEN = (
    "comedy", "drama", "documentary", "romance", "biographical", "biopic",
    "historical", "history", "mystery", "science fiction", "sci-fi", "fantasy",
    "adventure", "superhero", "sport", "coming-of-age", "musical", "teen",
    "road movie", "satire",
)


def _matches(genres_lower: list[str], keywords) -> bool:
    return any(any(k in g for k in keywords) for g in genres_lower)


def min_age(genres: list[str]) -> int:
    """Estimate the minimum appropriate age from a film's genres."""
    g = [x.lower() for x in genres]
    if _matches(g, _ADULT):
        return 18
    if _matches(g, _MATURE):
        return 16
    if _matches(g, _KID):
        return 5
    if _matches(g, _TWEEN):
        return 12
    return 16  # unknown / unrecognised genres: assume mature, not kid-safe


def age_tags(genres: list[str]) -> list[str]:
    """Return the age-appropriateness tags for a film's genres."""
    age = min_age(genres)
    if age <= 5:
        return [AGE_5, AGE_12]
    if age <= 12:
        return [AGE_12]
    if age < 18:
        return [AGE_16]
    return [AGE_18]
