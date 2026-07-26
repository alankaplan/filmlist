"""Fetch festival award winners from Wikidata.

Wikidata models "award received" (P166) statements on film entities, so a
single SPARQL query returns every winner of a given festival award, along
with the director, country of origin, and the year it won (the point-in-time
qualifier on the award statement).

We match the award by its English label rather than a hard-coded Q-number so
the mapping is legible and easy to correct. Network access is injectable via
the ``fetcher`` argument, which keeps the parsing logic testable offline.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from typing import Callable, Optional

from .models import Film

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Wikidata requires a descriptive User-Agent identifying the application.
USER_AGENT = "filmlist/0.1 (https://github.com/alankaplan/filmlist)"

# The proxy in some environments performs TLS interception; trusting this
# bundle (in addition to the system store) lets HTTPS verification succeed.
_PROXY_CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

# Map each festival to the English label of its top competitive award.
# Festivals whose award is cleanly labelled on Wikidata resolve reliably;
# Sundance/Toronto use best-effort labels and can be refined.
FESTIVAL_AWARD_LABELS: dict[str, str] = {
    "Cannes": "Palme d'Or",
    "Venice": "Golden Lion",
    "Berlin": "Golden Bear",
    "Locarno": "Golden Leopard",
    "San Sebastian": "Golden Shell",
    "Sundance": "Grand Jury Prize: Dramatic",
    "Toronto": "People's Choice Award",
    # Telluride is non-competitive — no jury award to query.
}


class FetchError(RuntimeError):
    """Raised when a Wikidata query cannot be completed."""


def build_query(award_label: str, since: Optional[int] = None) -> str:
    """Return a SPARQL query for all films that received ``award_label``."""
    since_filter = f"  FILTER(?year >= {int(since)})" if since else ""
    # The award is identified by its exact English label; the year comes from
    # the point-in-time (P585) qualifier on the award statement, falling back
    # to the film's publication date (P577). Directors/countries are
    # aggregated so each film yields a single row.
    return f"""
SELECT ?filmLabel ?year
       (GROUP_CONCAT(DISTINCT ?directorLabel; separator=", ") AS ?directors)
       (GROUP_CONCAT(DISTINCT ?countryLabel;  separator=", ") AS ?countries)
WHERE {{
  ?award rdfs:label {json.dumps(award_label)}@en .
  ?film p:P166 ?awardStat .
  ?awardStat ps:P166 ?award .
  OPTIONAL {{ ?awardStat pq:P585 ?when . }}
  OPTIONAL {{ ?film wdt:P577 ?released . }}
  BIND(YEAR(COALESCE(?when, ?released)) AS ?year)
  OPTIONAL {{ ?film wdt:P57 ?director .
             ?director rdfs:label ?directorLabel . FILTER(LANG(?directorLabel)="en") }}
  OPTIONAL {{ ?film wdt:P495 ?country .
             ?country rdfs:label ?countryLabel . FILTER(LANG(?countryLabel)="en") }}
  ?film rdfs:label ?filmLabel . FILTER(LANG(?filmLabel)="en")
{since_filter}
}}
GROUP BY ?filmLabel ?year
ORDER BY DESC(?year)
""".strip()


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = os.environ.get("SSL_CERT_FILE") or _PROXY_CA_BUNDLE
    if ca and os.path.exists(ca):
        try:
            ctx.load_verify_locations(ca)
        except (ssl.SSLError, OSError):
            pass
    return ctx


def _http_get(url: str, params: dict) -> dict:
    """Perform the SPARQL GET request and return parsed JSON.

    urllib honours the HTTP(S)_PROXY environment variables automatically."""
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        raise FetchError(f"Wikidata returned HTTP {exc.code}: {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:  # pragma: no cover
        raise FetchError(f"Could not reach Wikidata: {exc}") from exc


def _parse_results(data: dict, festival: str, award_label: str) -> list[Film]:
    films: list[Film] = []
    for binding in data.get("results", {}).get("bindings", []):
        title = binding.get("filmLabel", {}).get("value", "").strip()
        year_raw = binding.get("year", {}).get("value", "").strip()
        if not title or not year_raw:
            continue
        try:
            year = int(year_raw)
        except ValueError:
            continue
        if not (1888 <= year <= 2100):
            continue
        try:
            films.append(
                Film(
                    title=title,
                    year=year,
                    festival=festival,
                    director=binding.get("directors", {}).get("value", "").strip(),
                    country=binding.get("countries", {}).get("value", "").strip(),
                    award=award_label,
                )
            )
        except ValueError:
            # Skip any row that doesn't form a valid Film.
            continue
    return films


def fetch_award_winners(
    festival: str,
    since: Optional[int] = None,
    endpoint: str = WIKIDATA_ENDPOINT,
    fetcher: Callable[[str, dict], dict] = _http_get,
) -> list[Film]:
    """Fetch all award winners for a single festival from Wikidata."""
    award_label = FESTIVAL_AWARD_LABELS.get(festival)
    if not award_label:
        raise FetchError(
            f"No award mapping for festival {festival!r}. "
            f"Known: {', '.join(sorted(FESTIVAL_AWARD_LABELS))}"
        )
    query = build_query(award_label, since=since)
    data = fetcher(endpoint, {"query": query, "format": "json"})
    return _parse_results(data, festival, award_label)


def fetch_all_awards(
    since: Optional[int] = None,
    endpoint: str = WIKIDATA_ENDPOINT,
    fetcher: Callable[[str, dict], dict] = _http_get,
) -> list[Film]:
    """Fetch award winners across every mapped festival."""
    films: list[Film] = []
    for festival in FESTIVAL_AWARD_LABELS:
        films.extend(
            fetch_award_winners(festival, since=since, endpoint=endpoint, fetcher=fetcher)
        )
    return films
