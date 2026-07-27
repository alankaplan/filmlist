# filmlist

A small app that maintains a database of movies from major international film
festivals and generates a self-contained, filterable HTML page from it.

Every film shown on the page is fetched automatically from **Wikidata** (with
plot summaries from **Wikipedia**) — nothing is hand-authored. It covers award
winners from **Cannes, Venice, Berlin, Sundance, SXSW, Toronto, Locarno,** and
**San Sebastián**, and the generated page can be filtered by **festival, year,
and genre**.

## Requirements

- Python 3.9+ (standard library only — SQLite ships with Python)
- Outbound HTTPS to `query.wikidata.org` and `en.wikipedia.org` for `pull`
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
| `delete ID` | Remove a film by its id. |
| `generate [-o OUTPUT] [--include-manual]` | Render the database to an HTML page. |

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
  models.py      # Film dataclass (incl. genre) + festival list & validation
  db.py          # SQLite persistence (source tracking, merge/overwrite upserts)
  fetch.py       # Wikidata award fetcher + Wikipedia summary enrichment
  generate.py    # HTML page renderer with festival/year/genre filters
  cli.py         # argparse command-line interface
tests/           # pytest suite
main.py          # entry point
```

## Development

```bash
pip install pytest
pytest
```
