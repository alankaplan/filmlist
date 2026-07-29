"""A small TMDB (The Movie Database) client for content signals.

We use TMDB for two things that make age assessment reliable:

* official age **certifications** (`/movie/{id}/release_dates`), and
* content **keywords** (`/movie/{id}/keywords`).

Films are linked to TMDB by their TMDB id (Wikidata P4947) when available, or
by their IMDb id (P345) via `/find`. Network access is injectable via the
``fetcher`` argument (same pattern as ``fetch.py``) so parsing stays testable
offline. Per-lookup failures are swallowed and reported as "no data" so a
single bad film never aborts a pull.

This product uses the TMDB API but is not endorsed or certified by TMDB.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from .fetch import FetchError, _http_get

TMDB_API = "https://api.themoviedb.org/3"

# Country certification systems, in the order we prefer them.
_COUNTRY_PREFERENCE = ["US", "GB"]

Fetcher = Callable[[str, dict], dict]


def api_key() -> Optional[str]:
    """The TMDB v3 API key from the environment, or None if unset."""
    key = os.environ.get("TMDB_API_KEY", "").strip()
    return key or None


def resolve_id(
    tmdb_id: str,
    imdb_id: str,
    key: str,
    fetcher: Fetcher = _http_get,
) -> Optional[str]:
    """Return a TMDB movie id, using the TMDB id directly or resolving the
    IMDb id via /find. Returns None when neither yields a match."""
    if tmdb_id:
        return str(tmdb_id)
    if imdb_id:
        data = fetcher(
            f"{TMDB_API}/find/{imdb_id}",
            {"external_source": "imdb_id", "api_key": key},
        )
        results = data.get("movie_results") or []
        if results:
            return str(results[0].get("id"))
    return None


def certification(
    movie_id: str, key: str, fetcher: Fetcher = _http_get
) -> Optional[tuple[str, str]]:
    """Return a ``(country, rating)`` certification, preferring US then GB
    then any other country with a non-empty rating. None if unavailable."""
    data = fetcher(f"{TMDB_API}/movie/{movie_id}/release_dates", {"api_key": key})
    by_country: dict[str, str] = {}
    for entry in data.get("results", []):
        country = entry.get("iso_3166_1", "")
        for rel in entry.get("release_dates", []):
            cert = (rel.get("certification") or "").strip()
            if cert and country not in by_country:
                by_country[country] = cert
    for country in _COUNTRY_PREFERENCE:
        if country in by_country:
            return country, by_country[country]
    for country, cert in by_country.items():
        return country, cert
    return None


def keywords(movie_id: str, key: str, fetcher: Fetcher = _http_get) -> list[str]:
    """Return the film's TMDB keywords as lowercased strings."""
    data = fetcher(f"{TMDB_API}/movie/{movie_id}/keywords", {"api_key": key})
    return [k.get("name", "").lower() for k in data.get("keywords", []) if k.get("name")]


def content_signals(
    tmdb_id: str,
    imdb_id: str,
    key: str,
    fetcher: Fetcher = _http_get,
) -> tuple[Optional[str], list[str]]:
    """Best-effort ``(rating, keywords)`` for a film.

    ``rating`` is the bare certification string (e.g. "PG-13"); either result
    may be empty when TMDB has no data or a lookup fails."""
    try:
        movie_id = resolve_id(tmdb_id, imdb_id, key, fetcher)
        if not movie_id:
            return None, []
        cert = certification(movie_id, key, fetcher)
        rating = cert[1] if cert else None
        return rating, keywords(movie_id, key, fetcher)
    except (FetchError, KeyError, IndexError, ValueError):
        return None, []
