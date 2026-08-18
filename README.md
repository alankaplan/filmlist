# filmlist

A small app that maintains a database of movies from major international film
festivals and generates a self-contained, filterable HTML page from it.

Every film shown on the page is fetched automatically from **Wikidata** (with
plot summaries from **Wikipedia**) — nothing is hand-authored. It covers award
winners from **Cannes, Venice, Berlin, Sundance, SXSW, Toronto, Locarno,**
**San Sebastián,** and the **Oscars**. The generated page has **additive,
multi-select filters** for **festival, year, genre, and tags** — pick several
values in a filter to widen the results, and combine filters to narrow them —
plus a **Sort** control (by year, title, or Rotten Tomatoes rating). A film is
identified by its title, so a movie that played several festivals — or that
premiered one year and won an award in another (e.g. an Oscar the following
season) — is shown as a **single item** that names each festival and year in
its expanded view. Where Wikidata records it, each film also shows its **Rotten
Tomatoes Tomatometer** score.

You can **mark films as watched** right on the page — a toggle on each row —
and a **Show** control views All / Unwatched / Watched with a running watched
count. Watched state is saved in your **browser** (`localStorage`), so it
survives reloads and page regeneration but is per-device and never leaves your
machine (nothing is synced or committed).

Every film is also **auto-tagged for age appropriateness** — specifically for a
**5-year-old** and a **12-year-old** — from official **TMDB** age
certifications (refined by content keywords). Films with no certification are
marked `Unrated` rather than guessed, so a positive tag is never wrong.

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

Each film is tagged from **real age certifications only** — a positive tag is
never a guess:

| Tag | Meaning |
| --- | --- |
| `OK for 5` | Certified suitable for a 5-year-old (also implies `OK for 12`). |
| `OK for 12` | Certified suitable for a 12-year-old. |
| _(neither)_ | Rated, but too mature for both — no age tag shown. |
| `Unrated` | No age certification found — appropriateness is **not** asserted. |

How a film is assessed (see `filmlist/tagging.py`):

1. **Official age certification** from TMDB (`/movie/{id}/release_dates`),
   mapped to a minimum age — e.g. G/U → *OK for 5*; PG, 12/12A → *OK for 12*;
   PG-13, R and up → neither. Thresholds follow each rating body's own guidance.
2. **Content keywords** from TMDB (nudity, graphic violence, drugs…) — these
   only ever *tighten* a certification, never loosen it.

**Genre is deliberately not used to grant an age tag.** An arthouse "drama" is
not automatically fit for a 12-year-old, and guessing from genre produced
confidently wrong tags — so a film with no certification is simply `Unrated`.

Films are linked to TMDB via their Wikidata TMDB id (P4947) or IMDb id (P345),
and, failing that, by a **title + year search** (exact title, release year
within one) so foreign/festival titles still get rated. Set the API key:

```bash
export TMDB_API_KEY=your_v3_api_key
python main.py pull 2024        # "TMDB enrichment: on"
```

Without a key, `pull` still runs but every film is `Unrated`. Re-running `pull`
with a key is what fetches real ratings; `python main.py retag` only normalizes
tags offline (it cannot fetch certifications). You can also attach your own tags
to a hand-added film with `add ... --tags "must-watch"`.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

### Rotten Tomatoes scores

Each film shows its **Rotten Tomatoes Tomatometer** percentage where one is
available, and the page can be **sorted by rating** (high or low; films without
a score sort last). Rotten Tomatoes has no usable public API, so the score is
read from **Wikidata** — a "review score" statement (P444) whose "review score
by" qualifier (P447) is Rotten Tomatoes — in the same `pull` query as everything
else. A film often carries a second such statement for the critics' *average
rating* (e.g. `8.4/10`); the query keeps only the percentage form, so it's the
Tomatometer that's shown, never the average. No API key is needed. Two caveats:

- **Partial coverage.** Only films whose Tomatometer an editor has recorded on
  Wikidata will show one; the rest simply omit the badge.
- **A snapshot, not live.** It reflects whatever was last entered on Wikidata,
  not the current Tomatometer. The score is stored at pull time, so films pulled
  by an older version keep their value until you re-run `pull <year>`.

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
- **The Oscars** are pulled as a "festival" too, but only the film-level
  categories (Best Picture, Animated/International/Documentary Feature) — acting
  and directing awards go to people, not films. Oscars are keyed by **ceremony
  year**, so `pull 2024 --festival Oscars` returns the 2024-ceremony winners.
  Because the page identifies a film by title, an Oscar winner is **merged into
  the same item** as its festival premiere (usually the prior year); the
  expanded view lists each award with its own festival and year.
- **No API key** is needed.
- Pulls are **merge-only**: they fill blank fields but never overwrite existing
  data, and re-running only adds newly recorded winners.
- The generated page shows **only automatically pulled films**. Hand-added
  films (`add`) are stored with a `manual` source and omitted unless you pass
  `--include-manual`.
- Requires outbound HTTPS. In restricted network environments the command
  fails with a clear message instead of a traceback.
- Each film's **full Wikipedia intro** is stored as its description (shown when
  a row is expanded). Descriptions are saved at pull time, so films pulled by an
  older version keep their truncated text until you re-run `pull`.
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
  tmdb.py        # TMDB client: age certifications, keywords, title+year search
  tagging.py     # age tagging from certification + keywords (else "Unrated")
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
