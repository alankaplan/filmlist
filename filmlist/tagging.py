"""Automatic age-appropriateness tagging for films.

Every film is assessed for exactly two ages — 5 and 12 — using **only** a real
age certification, so a positive tag is never a guess:

    "OK for 5"   suitable for a five-year-old   (implies "OK for 12")
    "OK for 12"  suitable for a twelve-year-old
    (neither)    rated, but too mature for both
    "Unrated"    no age certification available — appropriateness not asserted

The signals, in order:

    1. an official age certification (TMDB, via /movie/{id}/release_dates) —
       the sole source of a positive "OK for …" tag
    2. content keywords (TMDB) — these only ever tighten the certification

Genre is deliberately NOT used to grant an age tag: it is far too weak (an
arthouse "drama" is not automatically fit for a 12-year-old), and doing so
produced confidently wrong results. A film with no certification is "Unrated".

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
UNRATED = "Unrated"

# The positive age tags (green styling). "Unrated" is intentionally excluded so
# it renders as a neutral pill and is never mistaken for an assurance.
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


def age_tags(
    genres: Optional[list[str]] = None,
    certification: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[str]:
    """Return the age tags for a film.

    A positive "OK for …" tag comes only from a real age certification
    (keywords may tighten it). Without a certification the film is "Unrated" —
    genre is never used to assert appropriateness. ``genres`` is accepted for a
    stable call signature but is intentionally unused."""
    cert_age = cert_min_age(certification)
    if cert_age is None:
        return [UNRATED]

    base = max(cert_age, keyword_floor(keywords))
    tags: list[str] = []
    if base <= 12:
        tags.append(AGE_12)
    if base <= 5:
        tags.insert(0, AGE_5)
    return tags
