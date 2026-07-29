"""Automatic age-appropriateness tagging for films.

Every film is assessed for exactly two ages — 5 and 12 — and tagged with
whichever it passes:

    "OK for 5"   suitable for a five-year-old   (implies "OK for 12")
    "OK for 12"  suitable for a twelve-year-old
    (neither)    too mature for both

The assessment prefers real data, in this order:

    1. an official age certification (TMDB, via /movie/{id}/release_dates)
    2. content keywords (TMDB) — these only ever tighten the rating
    3. a genre heuristic, as a last resort so nothing goes unassessed

Certifications and keywords come from :mod:`filmlist.tmdb`; the mapping tables
below turn them into a minimum appropriate age. Thresholds mirror each rating
body's own guidance (e.g. BBFC PG "should not unsettle a child aged around
eight or older"), so "OK for 5" resolves to G/U only and "OK for 12" to
G/U/PG/12/12A.
"""

from __future__ import annotations

import re
from typing import Optional

AGE_5 = "OK for 5"
AGE_12 = "OK for 12"

# All age tags, youngest-friendly first (used to build filter options/order).
AGE_TAGS = [AGE_5, AGE_12]

# Age tags emitted by earlier versions; stripped when retagging so upgrades
# don't leave stale "16+"/"18+" chips behind.
OBSOLETE_AGE_TAGS = ["16+", "18+"]

# --- certification -> minimum appropriate age -----------------------------
# Keys are upper-cased certification strings as TMDB returns them.
_CERT_MIN_AGE = {
    # US MPAA
    "G": 0, "PG": 8, "PG-13": 13, "R": 17, "NC-17": 18,
    # UK BBFC
    "U": 0, "12": 12, "12A": 12, "15": 15, "18": 18, "R18": 18,
    # (BBFC "PG" shares the MPAA "PG" entry above.)
}


def cert_min_age(rating: Optional[str]) -> Optional[int]:
    """Map a certification string to a minimum age, or None if unrecognised."""
    if not rating:
        return None
    r = rating.strip().upper()
    if r in _CERT_MIN_AGE:
        return _CERT_MIN_AGE[r]
    # Many countries use a bare numeric age (e.g. "16").
    if re.fullmatch(r"\d{1,2}", r):
        return int(r)
    return None


# --- content keywords -> strictness floor ---------------------------------
# Keywords only ever RAISE the age; they never grant young-safety.
_KW_HARD = (
    "graphic violence", "gore", "torture", "rape", "sexual violence",
    "explicit sex", "pornography", "incest", "sexual abuse", "snuff",
)
_KW_MODERATE = (
    "nudity", "sex scene", "strong violence", "drug abuse", "prostitution",
    "heroin", "cocaine",
)


def keyword_floor(keywords: Optional[list[str]]) -> int:
    """Minimum age implied by mature content keywords (0 if none match)."""
    if not keywords:
        return 0
    joined = [k.lower() for k in keywords]
    if any(any(h in k for h in _KW_HARD) for k in joined):
        return 18
    if any(any(m in k for m in _KW_MODERATE) for k in joined):
        return 12
    return 0


# --- genre heuristic (fallback) -------------------------------------------
_ADULT = ("porn", "erotic", "hardcore", "exploitation", "slasher", "splatter",
          "giallo", "snuff")
_MATURE = ("horror", "thriller", "crime", "war", "noir", "gangster", "action",
           "western", "martial arts", "disaster", "zombie", "vampire")
_KID = ("animation", "animated", "family", "children", "stop motion",
        "computer animation")
_TWEEN = ("comedy", "drama", "documentary", "romance", "biographical", "biopic",
          "historical", "history", "mystery", "science fiction", "sci-fi",
          "fantasy", "adventure", "superhero", "sport", "coming-of-age",
          "musical", "teen", "road movie", "satire")


def _matches(genres_lower: list[str], keywords) -> bool:
    return any(any(k in g for k in keywords) for g in genres_lower)


def genre_min_age(genres: list[str]) -> int:
    """Estimate a minimum appropriate age from genres (fallback signal)."""
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


def age_tags(
    genres: list[str],
    certification: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[str]:
    """Return the age tags for a film, combining the available signals.

    Certification is authoritative when present; keywords can only tighten it;
    genre is the fallback when no certification is available."""
    kw_floor = keyword_floor(keywords)
    cert_age = cert_min_age(certification)

    if cert_age is not None:
        base = max(cert_age, kw_floor)
    elif kw_floor > 0:
        base = max(kw_floor, genre_min_age(genres))
    else:
        base = genre_min_age(genres)

    tags: list[str] = []
    if base <= 12:
        tags.append(AGE_12)
    if base <= 5:
        tags.insert(0, AGE_5)
    return tags
