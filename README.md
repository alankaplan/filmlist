# filmlist

A small app that maintains a database of movies from major international film
festivals and generates a self-contained, filterable HTML page from it.

Every film shown on the page is fetched automatically from **Wikidata** (with
plot summaries from **Wikipedia**) — nothing is hand-authored. It covers award
winners from **Cannes, Venice, Berlin, Sundance, SXSW, Toronto, Locarno,** and
**San Sebastián**. The generated page has **additive, multi-select filters**
for **festival, year, genre, and tags** — pick several values in a filter to
widen the results, and combine filters to narrow them.

Every film is also **auto-tagged for age appropriateness** — specifically for a
**5-year-old** and a **12-year-old** — using official age certifications and
content keywords from **TMDB** when available, falling back to genre.

## Requirements

- Python 3.9+ (standard library only — SQLite ships with Python)
- Outbound HTTPS to `query.wikidata.org` and `en.wikipedia.org` for `pull`
- Optional: a free **TMDB API key** (`TMDB_API_KEY`) for reliable age tags
- `pytest` only if you want to run the tests

## Quick start

```bash
# 1. Pull a year's festival award winners into a local SQLite DB
python main.py pull 2023

# 2. Generate the HTML page (shows only pulled films)
python main.py generate -o index.html

# 3. Open index.html in your browser
```

Pull the years you care about (one per run) before generating:

```bash
python main.py pull 2024
python main.py pull 2023
python main.py pull 2022 --festival Cannes
python main.py generate -o index.html
```

## Usage

All commands share an optional `--db PATH` flag (defaults to `filmlist.db`).

| Command | Description |
| --- | --- |
| `pull YEAR [--festival F]` | Fetch that year's award winners from Wikidata (one year per run). |
| `list [--festival F] [--year Y] [--include-manual]` | List films (pulled only by default). |
| `add TITLE YEAR FESTIVAL [options]` | Add a film by hand (excluded from the page unless `--include-manual`). |
| `retag` | Recompute automatic age tags for every film from its genres. |
| `delete ID` | Remove a film by its id. |
| `generate [-o OUTPUT] [--include-manual]` | Render the database to an HTML page. |

### Age appropriateness (5 and 12)

Every film is assessed for two ages and tagged with whichever it passes:

| Tag | Meaning |
| --- | --- |
| `OK for 5` | Suitable for a 5-year-old (also implies `OK for 12`). |
| `OK for 12` | Suitable for a 12-year-old. |
| _(neither)_ | Too mature for both — no age tag shown. |

The assessment prefers real data, in this order (see `filmlist/tagging.py`):

1. **Official age certification** from TMDB (`/movie/{id}/release_dates`),
   mapped to a minimum age — e.g. G/U → *OK for 5*; PG, 12/12A → *OK for 12*;
   PG-13, R and up → neither. Thresholds follow each rating body's own
   guidance.
2. **Content keywords** from TMDB (nudity, graphic violence, drugs…) — these
   only ever *tighten* the rating, never loosen it.
3. **Genre heuristic** as a last resort, so films with no TMDB data still get
   assessed.

Films are linked to TMDB via their Wikidata TMDB id (P4947) or IMDb id (P345),
so no title guessing is needed. Set the API key to enable it:

```bash
export TMDB_API_KEY=your_v3_api_key
python main.py pull 2024        # "TMDB enrichment: on"
```

Without a key, `pull` still works and falls back to the genre-based estimate
(the age tags are then a rough heuristic, not an official rating). Re-running
`pull` refreshes the TMDB-based tags; `python main.py retag` recomputes the
genre-based fallback for rows already in the database. You can also attach your
own tags to a hand-added film with `add ... --tags "must-watch"`.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

### Pulling award winners

The app populates itself from Wikidata's "award received" statements and
enriches each film with genre (P136) and a plain-text intro summary from the
English Wikipedia article:

```bash
python main.py pull 2023                    # all mapped festivals, 2023
python main.py pull 2023 --festival Venice  # just Venice, 2023
```

Notes:

- **One year per run**, given as a positional argument, so you decide exactly
  which editions land in the database.
- **Multiple awards per festival** are pulled (e.g. Cannes' Palme d'Or, Grand
  Prix, Jury Prize, Best Director, Best Screenplay). The award list lives in
  `FESTIVAL_AWARDS` in `filmlist/fetch.py` and is easy to extend — awards are
  matched by English label or alias, case-insensitively.
- **No API key** is needed.
- Pulls are **merge-only**: they fill blank fields but never overwrite existing
  data, and re-running only adds newly recorded winners.
- The generated page shows **only automatically pulled films**. Hand-added
  films (`add`) are stored with a `manual` source and omitted unless you pass
  `--include-manual`.
- Requires outbound HTTPS. In restricted network environments the command
  fails with a clear message instead of a traceback.
- This fetches *award winners*, not full official selections — complete
  lineups live in Wikipedia tables and would need a separate, per-festival
  parser.

## Project layout

```
filmlist/
  __init__.py
  models.py      # Film dataclass (incl. genre, tags) + festival list & validation
  db.py          # SQLite persistence (source tracking, migrations, upserts)
  fetch.py       # Wikidata award fetcher + Wikipedia summary enrichment
  tmdb.py        # TMDB client: age certifications + content keywords
  tagging.py     # age tagging from certification, keywords, then genre
  generate.py    # HTML page renderer with additive festival/year/genre/tag filters
  cli.py         # argparse command-line interface
tests/           # pytest suite
main.py          # entry point
```

## Development

```bash
pip install pytest
pytest
```
