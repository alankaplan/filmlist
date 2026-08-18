"""Render the film database to a single, self-contained HTML page.

The page is a compact list — one line per movie (title, festival(s), year,
award and age tag) that expands on click to show the full details. A film that
played several festivals is merged into a single item naming each. Four
additive, multi-select filters: festival, year, genre, and tag. Within a
filter, selecting several values widens the results (OR); across filters they
narrow (AND). Expand/collapse uses native <details>/<summary>, so no extra JS."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from .models import Film, parse_rt_percent
from .tagging import AGE_TAGS, UNRATED

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Film Festival Database</title>
<style>
:root {{
  --bg: #0f1115; --panel: #171a21; --line: #262b36;
  --text: #e8eaed; --muted: #9aa3b2; --accent: #e5b567; --chip: #222735;
  --age: #6fbf9b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI",
  Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text);
}}
header {{
  padding: 2.4rem 1.5rem 1.6rem; border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, #12151c, var(--bg));
}}
header .wrap {{ max-width: 1000px; margin: 0 auto; }}
h1 {{ margin: 0 0 .3rem; font-size: 1.9rem; letter-spacing: .5px; }}
h1 .accent {{ color: var(--accent); }}
.sub {{ color: var(--muted); font-size: .95rem; }}
main {{ max-width: 1000px; margin: 0 auto; padding: 1.5rem; }}
.controls {{
  margin: 0 0 1.6rem; padding: 1rem 1.1rem; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px;
}}
.facets {{ display: flex; flex-wrap: wrap; gap: .6rem; }}
/* One checkbox dropdown per filter. */
.dd {{ position: relative; }}
.dd > summary {{
  list-style: none; cursor: pointer; user-select: none;
  border: 1px solid var(--line); background: var(--chip); color: var(--text);
  padding: .4rem .8rem; border-radius: 8px; font-size: .85rem;
  display: inline-flex; align-items: center; gap: .4rem;
}}
.dd > summary::-webkit-details-marker {{ display: none; }}
.dd > summary::after {{ content: "\\25BE"; color: var(--muted); font-size: .7rem; }}
.dd[open] > summary, .dd > summary:hover {{ border-color: var(--accent); }}
.dd-count {{
  background: var(--accent); color: #1a1204; font-weight: 600; font-size: .7rem;
  border-radius: 999px; padding: .02rem .4rem;
}}
.dd-panel {{
  position: absolute; z-index: 20; top: calc(100% + .3rem); left: 0;
  min-width: 12rem; max-height: 16rem; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: .3rem; box-shadow: 0 8px 24px rgba(0,0,0,.4);
}}
.dd-opt {{
  display: flex; align-items: center; gap: .5rem; cursor: pointer;
  padding: .3rem .5rem; border-radius: 6px; font-size: .85rem; white-space: nowrap;
}}
.dd-opt:hover {{ background: var(--chip); }}
.dd-opt input {{ accent-color: var(--accent); width: 1rem; height: 1rem; }}
.toolbar {{ display: flex; align-items: center; gap: 1rem; margin-top: 1rem; padding-top: .8rem; border-top: 1px solid var(--line); }}
.sortbox {{ color: var(--muted); font-size: .82rem; display: inline-flex; align-items: center; gap: .4rem; }}
.sortbox select {{
  background: var(--chip); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: .3rem .5rem; font-size: .82rem;
}}
.sortbox select:focus {{ outline: none; border-color: var(--accent); }}
#count {{ color: var(--muted); font-size: .9rem; }}
#clear {{
  margin-left: auto; background: none; border: 1px solid var(--line); color: var(--muted);
  border-radius: 8px; padding: .3rem .7rem; font-size: .8rem; cursor: pointer;
}}
#clear:hover {{ border-color: var(--accent); color: var(--text); }}
.list {{ display: flex; flex-direction: column; gap: .35rem; }}
.item {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  transition: border-color .12s ease;
}}
.item:hover {{ border-color: var(--accent); }}
/* Compact one-line summary; click to expand. */
.item > summary {{
  list-style: none; cursor: pointer; display: flex; align-items: baseline;
  gap: .5rem; padding: .5rem .8rem;
}}
.item > summary::-webkit-details-marker {{ display: none; }}
.item > summary::before {{
  content: "\\25B8"; color: var(--muted); font-size: .7rem; flex: none;
}}
.item[open] > summary::before {{ content: "\\25BE"; }}
.s-main {{ flex: 1 1 auto; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.s-title {{ font-weight: 600; }}
.s-sub {{ color: var(--muted); font-size: .84rem; }}
.s-sub .fest {{ color: var(--accent); font-weight: 600; }}
.s-badges {{ margin-left: auto; display: flex; align-items: center; gap: .35rem; flex: none; }}
.s-badges .trophy {{ font-size: .8rem; }}
.age-chip {{
  font-size: .7rem; border-radius: 999px; padding: .05rem .5rem; white-space: nowrap;
  color: var(--muted); background: var(--chip); border: 1px solid var(--line);
}}
.age-chip.age {{ color: #062018; background: var(--age); border-color: var(--age); font-weight: 600; }}
.rt-chip {{
  font-size: .72rem; border-radius: 999px; padding: .05rem .5rem; white-space: nowrap;
  color: #2a0d08; background: #ff6347; border: 1px solid #ff6347; font-weight: 600;
}}
/* Per-film watched toggle (client-side, persisted in localStorage). */
.watch-btn {{
  font: inherit; font-size: .7rem; cursor: pointer; white-space: nowrap;
  border-radius: 999px; padding: .05rem .55rem; line-height: 1.4;
  color: var(--muted); background: var(--chip); border: 1px solid var(--line);
}}
.watch-btn:hover {{ border-color: var(--accent); color: var(--text); }}
.watch-btn .w-on {{ display: none; }}
.item.watched .watch-btn {{
  color: #062018; background: var(--age); border-color: var(--age); font-weight: 600;
}}
.item.watched .watch-btn .w-off {{ display: none; }}
.item.watched .watch-btn .w-on {{ display: inline; }}
/* Watched rows recede a little so the list reads as "done vs to-watch". */
.item.watched > summary .s-title {{ opacity: .55; text-decoration: line-through; }}
.item.watched > summary .s-sub {{ opacity: .55; }}
.details {{ padding: .1rem .8rem .75rem 1.7rem; }}
.details .meta {{ color: var(--muted); font-size: .86rem; margin: .3rem 0 0; }}
.details .meta .fest {{ color: var(--accent); font-weight: 600; }}
.details .award {{
  display: inline-block; font-size: .75rem; color: var(--accent); margin: .5rem 0 0;
  border: 1px solid var(--accent); border-radius: 6px; padding: .05rem .45rem;
}}
.taglist {{ display: flex; flex-wrap: wrap; gap: .3rem; margin: .5rem 0 0; }}
.taglist .g {{
  font-size: .72rem; color: var(--muted); background: var(--chip);
  border: 1px solid var(--line); border-radius: 999px; padding: .08rem .5rem;
}}
.taglist .age {{ color: #062018; background: var(--age); border-color: var(--age); font-weight: 600; }}
.details .synopsis {{ font-size: .9rem; color: #c7ccd6; margin: .5rem 0 0; }}
footer {{ color: var(--muted); text-align: center; padding: 2rem 1rem; font-size: .82rem; }}
.empty {{ color: var(--muted); padding: 3rem 0; text-align: center; }}
#noresults {{ display: none; }}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>Film Festival <span class="accent">Database</span></h1>
  <div class="sub">{count} films across {fest_count} festivals &middot; auto-pulled from Wikidata &middot; generated {today}</div>
</div></header>
<main>
  <div class="controls">
    <div class="facets">{facets}</div>
    <div class="toolbar">
      <label class="sortbox">Sort
        <select id="sort">
          <option value="year-desc">Year (newest)</option>
          <option value="year-asc">Year (oldest)</option>
          <option value="title-asc">Title (A&ndash;Z)</option>
          <option value="title-desc">Title (Z&ndash;A)</option>
          <option value="rt-desc">Rating (high)</option>
          <option value="rt-asc">Rating (low)</option>
        </select>
      </label>
      <label class="sortbox">Show
        <select id="watched-filter">
          <option value="all">All</option>
          <option value="unwatched">Unwatched</option>
          <option value="watched">Watched</option>
        </select>
      </label>
      <span id="count"></span>
      <button id="clear">Clear filters</button>
    </div>
  </div>
  {body}
  <div class="empty" id="noresults">No films match these filters.</div>
</main>
<footer>
  Built with filmlist &middot; a database of movies from major film festivals<br>
  Data from Wikidata &amp; Wikipedia. Age tags use the TMDB API but this product
  is not endorsed or certified by TMDB.
</footer>
<script>
const DIMS = ['festival', 'year', 'genre', 'tags'];
const active = {{festival: new Set(), year: new Set(), genre: new Set(), tags: new Set()}};
const items = Array.from(document.querySelectorAll('.item'));
const countEl = document.getElementById('count');
const noResults = document.getElementById('noresults');
const listEl = document.querySelector('.list');
const sortEl = document.getElementById('sort');
const watchedFilterEl = document.getElementById('watched-filter');

// --- watched state, persisted per-browser in localStorage -----------------
const WATCHED_STORE = 'filmlist:watched';
function loadWatched() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(WATCHED_STORE) || '[]')); }}
  catch (e) {{ return new Set(); }}
}}
function saveWatched() {{
  try {{ localStorage.setItem(WATCHED_STORE, JSON.stringify([...watched])); }}
  catch (e) {{ /* storage unavailable (private mode); session-only */ }}
}}
const watched = loadWatched();

function reflectWatched(item) {{
  const on = watched.has(item.dataset.watchKey);
  item.classList.toggle('watched', on);
  const btn = item.querySelector('.watch-btn');
  if (btn) btn.setAttribute('aria-pressed', on ? 'true' : 'false');
}}
items.forEach(item => {{
  reflectWatched(item);
  const btn = item.querySelector('.watch-btn');
  if (!btn) return;
  btn.addEventListener('click', e => {{
    // Inside <summary>, so keep the click from expanding the row.
    e.preventDefault();
    e.stopPropagation();
    const key = item.dataset.watchKey;
    if (watched.has(key)) watched.delete(key); else watched.add(key);
    saveWatched();
    reflectWatched(item);
    apply();
  }});
}});

function sortItems() {{
  if (!listEl) return;
  const mode = sortEl.value;
  const yr = el => +el.dataset.yearSort;
  const rt = el => +el.dataset.rt;   // -1 when the movie has no Tomatometer
  const cmp = {{
    'year-desc': (a, b) => (yr(b) - yr(a)) || a.dataset.title.localeCompare(b.dataset.title),
    'year-asc':  (a, b) => (yr(a) - yr(b)) || a.dataset.title.localeCompare(b.dataset.title),
    'title-asc': (a, b) => a.dataset.title.localeCompare(b.dataset.title) || (yr(b) - yr(a)),
    'title-desc':(a, b) => b.dataset.title.localeCompare(a.dataset.title) || (yr(b) - yr(a)),
    // Unscored films (rt = -1) always sort to the bottom, either direction.
    'rt-desc': (a, b) => (rt(b) - rt(a)) || a.dataset.title.localeCompare(b.dataset.title),
    'rt-asc':  (a, b) => ((rt(a) < 0) - (rt(b) < 0)) || (rt(a) - rt(b)) || a.dataset.title.localeCompare(b.dataset.title),
  }}[mode];
  items.slice().sort(cmp).forEach(el => listEl.appendChild(el));
}}
sortEl.addEventListener('change', sortItems);

function itemValues(item, dim) {{
  return (item.dataset[dim] || '').split('|').filter(Boolean);
}}

function apply() {{
  const view = watchedFilterEl.value;   // all | unwatched | watched
  let visible = 0, watchedTotal = 0;
  items.forEach(item => {{
    const facetOk = DIMS.every(dim => {{
      const sel = active[dim];
      return sel.size === 0 || itemValues(item, dim).some(v => sel.has(v));
    }});
    const isWatched = watched.has(item.dataset.watchKey);
    if (isWatched) watchedTotal++;
    const viewOk = view === 'all' || (view === 'watched') === isWatched;
    const ok = facetOk && viewOk;
    item.style.display = ok ? '' : 'none';
    if (ok) visible++;
  }});
  countEl.textContent =
    visible + ' of ' + items.length + ' films \\u00b7 ' + watchedTotal + ' watched';
  noResults.style.display = visible ? 'none' : '';
}}
watchedFilterEl.addEventListener('change', apply);

const dropdowns = Array.from(document.querySelectorAll('.dd'));

function updateCount(dd) {{
  const n = dd.querySelectorAll('input:checked').length;
  const badge = dd.querySelector('.dd-count');
  badge.textContent = n ? n : '';
  badge.style.display = n ? '' : 'none';
}}

dropdowns.forEach(dd => {{
  const dim = dd.dataset.dim;
  dd.querySelectorAll('.dd-panel input[type=checkbox]').forEach(box => {{
    box.addEventListener('change', () => {{
      if (box.checked) active[dim].add(box.value);
      else active[dim].delete(box.value);
      updateCount(dd);
      apply();
    }});
  }});
}});

// Close an open dropdown when clicking outside it, or on Escape.
document.addEventListener('click', e => {{
  dropdowns.forEach(dd => {{ if (dd.open && !dd.contains(e.target)) dd.open = false; }});
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') dropdowns.forEach(dd => {{ dd.open = false; }});
}});

document.getElementById('clear').addEventListener('click', () => {{
  DIMS.forEach(d => active[d].clear());
  dropdowns.forEach(dd => {{
    dd.querySelectorAll('input:checked').forEach(b => {{ b.checked = false; }});
    updateCount(dd);
    dd.open = false;
  }});
  apply();
}});

sortItems();
apply();
</script>
</body>
</html>
"""


def _esc(text: str) -> str:
    return html.escape(text or "")


def _dropdown(label: str, dim: str, values: Iterable) -> str:
    opts = "".join(
        f'<label class="dd-opt"><input type="checkbox" value="{_esc(str(v))}">'
        f'<span>{_esc(str(v))}</span></label>'
        for v in values
    )
    return (
        f'<details class="dd" data-dim="{dim}">'
        f'<summary class="dd-btn">{_esc(label)}<span class="dd-count" style="display:none"></span></summary>'
        f'<div class="dd-panel">{opts}</div>'
        f'</details>'
    )


@dataclass
class _Appearance:
    festival: str
    award: str
    section: str
    year: int


@dataclass
class MergedFilm:
    """One movie, possibly across several festivals and editions, for display."""

    title: str
    director: str = ""
    country: str = ""
    synopsis: str = ""
    rt_score: str = ""
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    appearances: list[_Appearance] = field(default_factory=list)

    @property
    def rt_percent(self) -> int | None:
        """The Tomatometer as an integer percentage, or None if unknown."""
        return parse_rt_percent(self.rt_score)

    @property
    def year(self) -> int:
        """The earliest (premiere) year the movie appears under."""
        return min(a.year for a in self.appearances)

    @property
    def years(self) -> list[int]:
        """Every distinct year the movie appears under, ascending."""
        return sorted({a.year for a in self.appearances})

    @property
    def festivals(self) -> list[str]:
        seen: list[str] = []
        for a in self.appearances:
            if a.festival not in seen:
                seen.append(a.festival)
        return seen


def _merge_films(films: Iterable[Film]) -> list[MergedFilm]:
    """Combine rows for the same movie across festivals *and* years.

    Identity is the movie's title (case-folded): a film's stored year is the
    pull year, which differs between its festival premiere and, say, its Oscar
    ceremony, so year is deliberately not part of the key. Each row becomes an
    appearance carrying its own festival/award/year; a movie that recurs under
    the same festival + award (e.g. from an ambiguous publication date) is
    collapsed to a single appearance keeping the earliest year."""
    order: list[str] = []
    by_key: dict[str, MergedFilm] = {}
    for f in films:
        key = f.title.casefold()
        m = by_key.get(key)
        if m is None:
            m = MergedFilm(
                title=f.title, director=f.director,
                country=f.country, synopsis=f.synopsis, rt_score=f.rt_score,
                genres=list(f.genres), tags=list(f.tag_list),
            )
            by_key[key] = m
            order.append(key)
        else:
            m.director = m.director or f.director
            m.country = m.country or f.country
            m.synopsis = m.synopsis or f.synopsis
            m.rt_score = m.rt_score or f.rt_score
            for g in f.genres:
                if g not in m.genres:
                    m.genres.append(g)
            for t in f.tag_list:
                if t not in m.tags:
                    m.tags.append(t)
        m.appearances.append(_Appearance(f.festival, f.award, f.section, f.year))

    for m in by_key.values():
        # Collapse duplicate editions of the same festival+award to one, keeping
        # the earliest year (e.g. a Cannes winner matched under two pull years).
        deduped: dict[tuple, _Appearance] = {}
        for a in m.appearances:
            k = (a.festival, a.award, a.section)
            if k not in deduped or a.year < deduped[k].year:
                deduped[k] = a
        # Chronological order so the premiere leads and badges read in sequence.
        m.appearances = sorted(deduped.values(), key=lambda a: (a.year, a.festival))
        # A real age tag on any festival row supersedes "Unrated" from another.
        if any(t in AGE_TAGS for t in m.tags):
            m.tags = [t for t in m.tags if t != UNRATED]
    return [by_key[k] for k in order]


def _render_item(film: MergedFilm) -> str:
    festivals = film.festivals
    years = film.years
    fest_html = " &middot; ".join(f'<span class="fest">{_esc(f)}</span>' for f in festivals)
    awarded = [a for a in film.appearances if a.award]
    year_label = str(years[0]) if len(years) == 1 else f"{years[0]}&ndash;{years[-1]}"
    rt = film.rt_percent

    # --- compact one-line summary ---
    trophy = ""
    if awarded:
        tip = "; ".join(f"{a.award} ({a.festival} {a.year})" for a in awarded)
        trophy = f'<span class="trophy" title="{_esc(tip)}">🏆</span>'
    rt_badge = f'<span class="rt-chip" title="Rotten Tomatoes">🍅 {rt}%</span>' if rt is not None else ""
    # Age-related tags (OK for 5/12 or Unrated) sit on the compact line.
    age_badges = "".join(
        f'<span class="age-chip{" age" if t in AGE_TAGS else ""}">{_esc(t)}</span>'
        for t in film.tags
        if t in AGE_TAGS or t == UNRATED
    )
    watch_btn = (
        '<button class="watch-btn" type="button" aria-pressed="false" '
        'title="Mark as watched"><span class="w-off">+ Watchlist</span>'
        '<span class="w-on">✓ Watched</span></button>'
    )
    summary = (
        f'<summary>'
        f'<span class="s-main"><span class="s-title">{_esc(film.title)}</span> '
        f'<span class="s-sub">&middot; {fest_html} &middot; {year_label}</span></span>'
        f'<span class="s-badges">{watch_btn}{rt_badge}{trophy}{age_badges}</span>'
        f'</summary>'
    )

    # --- expanded details ---
    meta_bits = [fest_html, year_label]
    if film.director:
        meta_bits.append(_esc(film.director))
    if film.country:
        meta_bits.append(_esc(film.country))
    if rt is not None:
        meta_bits.append(f'🍅 {rt}%')
    meta = " &middot; ".join(meta_bits)

    # A merged movie can span editions, so each award names its festival + year.
    award_html = "".join(
        f'<div class="award">🏆 {_esc(a.award)} &mdash; {_esc(a.festival)} {a.year}</div>'
        for a in awarded
    )

    pills = [f'<span class="g">{_esc(g)}</span>' for g in film.genres]
    for t in film.tags:
        cls = "g age" if t in AGE_TAGS else "g"
        pills.append(f'<span class="{cls}">{_esc(t)}</span>')
    pills_html = f'<div class="taglist">{"".join(pills)}</div>' if pills else ""
    synopsis_html = (
        f'<p class="synopsis">{_esc(film.synopsis)}</p>' if film.synopsis else ""
    )
    details = (
        f'<div class="details"><div class="meta">{meta}</div>'
        f"{award_html}{pills_html}{synopsis_html}</div>"
    )

    data_festival = _esc("|".join(festivals))
    data_year = _esc("|".join(str(y) for y in years))
    data_genre = _esc("|".join(film.genres))
    data_tags = _esc("|".join(film.tags))
    return (
        f'<details class="item" data-title="{_esc(film.title)}" '
        f'data-watch-key="{_esc(film.title.casefold())}" '
        f'data-festival="{data_festival}" '
        f'data-year="{data_year}" data-year-sort="{film.year}" '
        f'data-rt="{rt if rt is not None else -1}" '
        f'data-genre="{data_genre}" data-tags="{data_tags}">'
        f"{summary}{details}</details>"
    )


def _sort_tags(tags: set[str]) -> list[str]:
    """Age tags first (in age order), then any other tags alphabetically."""
    age = [t for t in AGE_TAGS if t in tags]
    other = sorted(t for t in tags if t not in AGE_TAGS)
    return age + other


def render_html(films: Iterable[Film]) -> str:
    """Return a complete HTML document for the given films."""
    merged = _merge_films(films)
    festivals: set[str] = set()
    genres: set[str] = set()
    tags: set[str] = set()
    years: set[int] = set()
    for m in merged:
        festivals.update(m.festivals)
        years.update(m.years)
        genres.update(m.genres)
        tags.update(m.tags)

    facets = "\n    ".join([
        _dropdown("Festival", "festival", sorted(festivals)),
        _dropdown("Year", "year", sorted(years, reverse=True)),
        _dropdown("Genre", "genre", sorted(genres)),
        _dropdown("Tags", "tags", _sort_tags(tags)),
    ])

    if not merged:
        body = '<div class="empty">No films yet. Run <code>filmlist pull &lt;year&gt;</code>.</div>'
    else:
        rows = "\n".join(_render_item(m) for m in merged)
        body = f'<div class="list">{rows}</div>'

    return PAGE_TEMPLATE.format(
        count=len(merged),
        fest_count=len(festivals),
        today=date.today().isoformat(),
        facets=facets,
        body=body,
    )


def write_html(films: Iterable[Film], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.write_text(render_html(films), encoding="utf-8")
    return out_path
