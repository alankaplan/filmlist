# filmlist

A small app that maintains a database of movies from major international film
festivals and generates a self-contained HTML page from it.

It tracks award winners and notable premieres from **Cannes, Venice, Berlin,
Sundance, Toronto, Locarno, San Sebastián,** and **Telluride**, and renders them
into a filterable, dependency-free web page.

## Requirements

- Python 3.9+ (standard library only — SQLite ships with Python)
- `pytest` only if you want to run the tests

## Quick start

```bash
# 1. Load the bundled seed data (real festival winners) into a local SQLite DB
python main.py seed

# 2. Generate the HTML page
python main.py generate -o index.html

# 3. Open index.html in your browser
```

## Usage

All commands share an optional `--db PATH` flag (defaults to `filmlist.db`).

| Command | Description |
| --- | --- |
| `seed [--file FILE]` | Load films from a JSON file (defaults to `data/seed.json`). |
| `add TITLE YEAR FESTIVAL [options]` | Add a single film. |
| `pull-awards [--festival F] [--since YEAR]` | Fetch award winners from Wikidata and merge them in. |
| `list [--festival F] [--year Y]` | List films, optionally filtered. |
| `delete ID` | Remove a film by its id. |
| `generate [-o OUTPUT]` | Render the database to an HTML page (default `index.html`). |

### Pulling award winners from Wikidata

The app can populate itself from Wikidata, which records "award received"
statements on film entities:

```bash
python main.py pull-awards                      # all mapped festivals
python main.py pull-awards --festival Cannes    # just the Palme d'Or winners
python main.py pull-awards --since 2015         # only recent winners
```

Notes:

- **No API key** is needed, and the query is matched by the award's English
  label (e.g. *Palme d'Or*, *Golden Lion*, *Golden Bear*), so the mapping in
  `filmlist/fetch.py` is easy to read and correct.
- Pulls are **merge-only**: they fill blank fields but never overwrite data
  you entered by hand, and re-running only adds newly recorded winners.
- Requires outbound HTTPS access to `query.wikidata.org`. In restricted
  network environments the command fails with a clear message instead of a
  traceback.
- This fetches *award winners*, not full official selections — festival
  lineups beyond the winners live in Wikipedia tables, which would need a
  separate, per-festival parser.

### Adding a film

```bash
python main.py add "Drive My Car" 2021 Cannes \
    --director "Ryusuke Hamaguchi" \
    --country Japan \
    --section "Competition" \
    --award "Best Screenplay" \
    --synopsis "A grieving stage director forms a bond with his reserved chauffeur."
```

Adds are idempotent on `(title, year, festival)`, so re-running the seed or
re-adding a film simply updates the existing record.

## Project layout

```
filmlist/
  __init__.py
  models.py      # Film dataclass + festival list & validation
  db.py          # SQLite persistence layer (overwrite + merge upserts)
  fetch.py       # Wikidata award-winner fetcher
  generate.py    # HTML page renderer
  cli.py         # argparse command-line interface
data/seed.json   # seed dataset of real festival films
tests/           # pytest suite
main.py          # entry point
```

## Development

```bash
pip install pytest
pytest
```
