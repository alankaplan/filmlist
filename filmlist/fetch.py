"""Fetch festival award winners from Wikidata (plus summaries from Wikipedia).

Wikidata models "award received" (P166) statements on film entities, so a
SPARQL query returns the winners of a festival's awards for a given year,
along with each film's director, country, genre, and English Wikipedia
article. A second pass fetches plain-text intro summaries from the MediaWiki
API for those articles.

Network access is injectable via the ``fetcher`` argument, which keeps the
query-building and parsing logic testable offline.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

from .models import Film

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# Wikidata requires a descriptive User-Agent identifying the application.
USER_AGENT = "filmlist/0.2 (https://github.com/alankaplan/filmlist)"

# The proxy in some environments performs TLS interception; trusting this
# bundle (in addition to the system store) lets HTTPS verification succeed.
_PROXY_CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

# How many characters of a Wikipedia intro we keep for a card summary.
_SUMMARY_LIMIT = 360

# Each festival maps to the English labels of the awards we pull. Matching is
# case-insensitive and also checks Wikidata aliases (skos:altLabel), so these
# need only be close to the canonical name. Edit freely to add awards.
FESTIVAL_AWARDS: dict[str, list[str]] = {
    "Cannes": [
        "Palme d'Or",
        "Grand Prix",
        "Jury Prize",
        "Prix de la mise en scène",
        "Best Screenplay Award",
    ],
    "Venice": [
        "Golden Lion",
        "Grand Jury Prize",
        "Silver Lion",
        "Volpi Cup for Best Actor",
        "Volpi Cup for Best Actress",
    ],
    "Berlin": [
        "Golden Bear",
        "Silver Bear Grand Jury Prize",
        "Silver Bear for Best Director",
        "Silver Bear Jury Prize",
    ],
    "Sundance": [
        "Grand Jury Prize: Dramatic",
        "Grand Jury Prize: Documentary",
        "Audience Award: Dramatic",
        "Directing Award: Dramatic",
    ],
    "SXSW": [
        "Grand Jury Award",
        "Audience Award",
    ],
    "Toronto": [
        "People's Choice Award",
        "Platform Prize",
    ],
    "Locarno": [
        "Golden Leopard",
        "Special Jury Prize",
    ],
    "San Sebastian": [
        "Golden Shell",
        "Silver Shell for Best Director",
    ],
    # Telluride is non-competitive — no jury award to query.
}


class FetchError(RuntimeError):
    """Raised when a remote query cannot be completed."""


# ---------------------------------------------------------------------------
# SPARQL query building / parsing
# ---------------------------------------------------------------------------
def build_query(award_labels: list[str], year: int) -> str:
    """Return a SPARQL query for a festival's award winners in ``year``.

    Awards are matched by their English label or alias (case-insensitive);
    the winning year comes from the award statement's point-in-time (P585)
    qualifier, falling back to the film's publication date (P577)."""
    values = " ".join(json.dumps(lbl) for lbl in award_labels)
    return f"""
SELECT ?award ?filmLabel ?article
       (SAMPLE(?descRaw) AS ?description)
       (GROUP_CONCAT(DISTINCT ?directorLabel; separator=", ") AS ?directors)
       (GROUP_CONCAT(DISTINCT ?countryLabel;  separator=", ") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?genreLabel;    separator=", ") AS ?genres)
WHERE {{
  VALUES ?award {{ {values} }}
  ?awardEntity rdfs:label|skos:altLabel ?awLabel .
  FILTER(LANG(?awLabel) = "en" && LCASE(STR(?awLabel)) = LCASE(?award))
  ?film p:P166 ?stat .
  ?stat ps:P166 ?awardEntity .
  OPTIONAL {{ ?stat pq:P585 ?when . }}
  OPTIONAL {{ ?film wdt:P577 ?released . }}
  BIND(YEAR(COALESCE(?when, ?released)) AS ?year)
  FILTER(?year = {int(year)})
  OPTIONAL {{ ?film wdt:P57 ?director .
             ?director rdfs:label ?directorLabel . FILTER(LANG(?directorLabel)="en") }}
  OPTIONAL {{ ?film wdt:P495 ?country .
             ?country rdfs:label ?countryLabel . FILTER(LANG(?countryLabel)="en") }}
  OPTIONAL {{ ?film wdt:P136 ?genre .
             ?genre rdfs:label ?genreLabel . FILTER(LANG(?genreLabel)="en") }}
  OPTIONAL {{ ?film schema:description ?descRaw . FILTER(LANG(?descRaw)="en") }}
  OPTIONAL {{ ?article schema:about ?film ;
                       schema:isPartOf <https://en.wikipedia.org/> . }}
  ?film rdfs:label ?filmLabel . FILTER(LANG(?filmLabel)="en")
}}
GROUP BY ?award ?filmLabel ?article
ORDER BY ?award ?filmLabel
""".strip()


def _title_from_article(url: str) -> str:
    """Derive a Wikipedia page title from its article URL."""
    if not url:
        return ""
    slug = url.rsplit("/wiki/", 1)[-1]
    return urllib.parse.unquote(slug).replace("_", " ")


def _parse_results(data: dict, festival: str, year: int) -> tuple[list[Film], dict[int, str]]:
    """Parse SPARQL JSON into Films. Returns the films and a map from each
    film's index to its Wikipedia article title (for summary enrichment)."""
    films: list[Film] = []
    article_titles: dict[int, str] = {}
    for binding in data.get("results", {}).get("bindings", []):
        title = binding.get("filmLabel", {}).get("value", "").strip()
        award = binding.get("award", {}).get("value", "").strip()
        if not title:
            continue
        description = binding.get("description", {}).get("value", "").strip()
        try:
            film = Film(
                title=title,
                year=year,
                festival=festival,
                director=binding.get("directors", {}).get("value", "").strip(),
                country=binding.get("countries", {}).get("value", "").strip(),
                genre=binding.get("genres", {}).get("value", "").strip(),
                award=award,
                synopsis=description,  # provisional; upgraded from Wikipedia
            )
        except ValueError:
            continue
        idx = len(films)
        films.append(film)
        article = _title_from_article(binding.get("article", {}).get("value", ""))
        if article:
            article_titles[idx] = article
    return films, article_titles


# ---------------------------------------------------------------------------
# Wikipedia summaries
# ---------------------------------------------------------------------------
def _truncate(text: str, limit: int = _SUMMARY_LIMIT) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;: ") + "…"


def fetch_summaries(
    titles: list[str],
    endpoint: str = WIKIPEDIA_API,
    fetcher: Optional[Callable[[str, dict], dict]] = None,
) -> dict[str, str]:
    """Fetch plain-text intro summaries for Wikipedia article titles."""
    fetcher = fetcher or _http_get
    titles = [t for t in dict.fromkeys(titles) if t]
    out: dict[str, str] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        data = fetcher(
            endpoint,
            {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": "1",
                "explaintext": "1",
                "redirects": "1",
                "titles": "|".join(batch),
            },
        )
        query = data.get("query", {})
        norm = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in query.get("redirects", [])}
        by_title = {
            p.get("title", ""): p.get("extract", "")
            for p in query.get("pages", {}).values()
        }
        for t in batch:
            resolved = redir.get(norm.get(t, t), norm.get(t, t))
            extract = by_title.get(resolved, "")
            if extract:
                out[t] = _truncate(extract)
    return out


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
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
    """Perform a GET request and return parsed JSON.

    urllib honours the HTTP(S)_PROXY environment variables automatically."""
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        raise FetchError(f"Server returned HTTP {exc.code}: {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:  # pragma: no cover
        raise FetchError(f"Could not reach {urllib.parse.urlparse(url).netloc}: {exc}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def fetch_award_winners(
    festival: str,
    year: int,
    endpoint: str = WIKIDATA_ENDPOINT,
    fetcher: Optional[Callable[[str, dict], dict]] = None,
    with_summaries: bool = True,
) -> list[Film]:
    """Fetch a single festival's award winners for a single year."""
    fetcher = fetcher or _http_get
    awards = FESTIVAL_AWARDS.get(festival)
    if not awards:
        raise FetchError(
            f"No award mapping for festival {festival!r}. "
            f"Known: {', '.join(sorted(FESTIVAL_AWARDS))}"
        )
    data = fetcher(endpoint, {"query": build_query(awards, year), "format": "json"})
    films, article_titles = _parse_results(data, festival, year)

    if with_summaries and article_titles:
        summaries = fetch_summaries(list(article_titles.values()), fetcher=fetcher)
        for idx, title in article_titles.items():
            if title in summaries:
                films[idx].synopsis = summaries[title]
    return films


def fetch_all_awards(
    year: int,
    endpoint: str = WIKIDATA_ENDPOINT,
    fetcher: Optional[Callable[[str, dict], dict]] = None,
    with_summaries: bool = True,
) -> list[Film]:
    """Fetch award winners across every mapped festival for a single year."""
    films: list[Film] = []
    for festival in FESTIVAL_AWARDS:
        films.extend(
            fetch_award_winners(
                festival,
                year,
                endpoint=endpoint,
                fetcher=fetcher,
                with_summaries=with_summaries,
            )
        )
    return films
