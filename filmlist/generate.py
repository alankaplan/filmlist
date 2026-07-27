"""Render the film database to a single, self-contained HTML page.

The page groups films by festival and offers three independent filters —
festival, year, and genre — applied together on the client."""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

from .models import Film

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
header .wrap {{ max-width: 1100px; margin: 0 auto; }}
h1 {{ margin: 0 0 .3rem; font-size: 1.9rem; letter-spacing: .5px; }}
h1 .accent {{ color: var(--accent); }}
.sub {{ color: var(--muted); font-size: .95rem; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 1.5rem; }}
.controls {{
  display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-end;
  margin: 0 0 1.6rem; padding: 1rem; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px;
}}
.field {{ display: flex; flex-direction: column; gap: .3rem; }}
.field label {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
.field select {{
  background: var(--chip); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: .45rem .7rem; font-size: .9rem; min-width: 150px;
}}
.field select:focus {{ outline: none; border-color: var(--accent); }}
#count {{ margin-left: auto; color: var(--muted); font-size: .9rem; align-self: center; }}
.fest {{ margin: 0 0 2.2rem; }}
.fest h2 {{ font-size: 1.25rem; margin: 0 0 .2rem; display: flex; align-items: baseline; gap: .6rem; }}
.fest h2 .count {{ font-size: .8rem; color: var(--muted); font-weight: 400; }}
.fest .bar {{ height: 2px; background: var(--accent); width: 44px; margin: 0 0 1rem; }}
.grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }}
.card {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem 1.1rem; transition: transform .12s ease, border-color .12s ease;
}}
.card:hover {{ transform: translateY(-2px); border-color: var(--accent); }}
.card .title {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 .15rem; }}
.card .meta {{ color: var(--muted); font-size: .85rem; margin: 0 0 .55rem; }}
.card .award {{
  display: inline-block; font-size: .78rem; color: var(--accent);
  border: 1px solid var(--accent); border-radius: 6px; padding: .1rem .45rem; margin: 0 0 .55rem;
}}
.genres {{ display: flex; flex-wrap: wrap; gap: .3rem; margin: 0 0 .55rem; }}
.genres .g {{
  font-size: .72rem; color: var(--muted); background: var(--chip);
  border: 1px solid var(--line); border-radius: 999px; padding: .08rem .5rem;
}}
.card .synopsis {{ font-size: .9rem; color: #c7ccd6; margin: .2rem 0 0; }}
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
    <div class="field">
      <label for="f-festival">Festival</label>
      <select id="f-festival"><option value="">All festivals</option>{festival_opts}</select>
    </div>
    <div class="field">
      <label for="f-year">Year</label>
      <select id="f-year"><option value="">All years</option>{year_opts}</select>
    </div>
    <div class="field">
      <label for="f-genre">Genre</label>
      <select id="f-genre"><option value="">All genres</option>{genre_opts}</select>
    </div>
    <div id="count"></div>
  </div>
  {body}
  <div class="empty" id="noresults">No films match these filters.</div>
</main>
<footer>Built with filmlist &middot; a database of movies from major film festivals</footer>
<script>
const filters = {{
  festival: document.getElementById('f-festival'),
  year: document.getElementById('f-year'),
  genre: document.getElementById('f-genre'),
}};
const cards = Array.from(document.querySelectorAll('.card'));
const sections = Array.from(document.querySelectorAll('.fest'));
const countEl = document.getElementById('count');
const noResults = document.getElementById('noresults');

function apply() {{
  const f = filters.festival.value, y = filters.year.value, g = filters.genre.value;
  let visible = 0;
  cards.forEach(card => {{
    const genres = (card.dataset.genre || '').split('|').filter(Boolean);
    const ok = (!f || card.dataset.festival === f)
            && (!y || card.dataset.year === y)
            && (!g || genres.includes(g));
    card.style.display = ok ? '' : 'none';
    if (ok) visible++;
  }});
  sections.forEach(sec => {{
    const anyVisible = sec.querySelector('.card:not([style*="display: none"])');
    sec.style.display = anyVisible ? '' : 'none';
  }});
  countEl.textContent = visible + ' of ' + cards.length + ' films';
  noResults.style.display = visible ? 'none' : '';
}}
Object.values(filters).forEach(sel => sel.addEventListener('change', apply));
apply();
</script>
</body>
</html>
"""


def _esc(text: str) -> str:
    return html.escape(text or "")


def _render_card(film: Film) -> str:
    meta_bits = [str(film.year)]
    if film.director:
        meta_bits.append(_esc(film.director))
    if film.country:
        meta_bits.append(_esc(film.country))
    if film.section:
        meta_bits.append(_esc(film.section))
    meta = " &middot; ".join(meta_bits)

    award_html = f'<div class="award">🏆 {_esc(film.award)}</div>' if film.award else ""
    genres = film.genres
    genre_html = ""
    if genres:
        chips = "".join(f'<span class="g">{_esc(g)}</span>' for g in genres)
        genre_html = f'<div class="genres">{chips}</div>'
    synopsis_html = (
        f'<p class="synopsis">{_esc(film.synopsis)}</p>' if film.synopsis else ""
    )
    # Genres are pipe-joined (and unescaped-safe as a data attribute value).
    data_genre = _esc("|".join(genres))
    return (
        f'<div class="card" data-festival="{_esc(film.festival)}" '
        f'data-year="{film.year}" data-genre="{data_genre}">'
        f'<div class="title">{_esc(film.title)}</div>'
        f'<div class="meta">{meta}</div>'
        f"{award_html}"
        f"{genre_html}"
        f"{synopsis_html}"
        "</div>"
    )


def _options(values: Iterable) -> str:
    return "".join(f'<option value="{_esc(str(v))}">{_esc(str(v))}</option>' for v in values)


def render_html(films: Iterable[Film]) -> str:
    """Return a complete HTML document for the given films."""
    films = list(films)
    by_fest: dict[str, list[Film]] = defaultdict(list)
    genres: set[str] = set()
    years: set[int] = set()
    for film in films:
        by_fest[film.festival].append(film)
        years.add(film.year)
        genres.update(film.genres)

    ordered_fests = sorted(by_fest, key=lambda f: (-len(by_fest[f]), f))

    festival_opts = _options(ordered_fests)
    year_opts = _options(sorted(years, reverse=True))
    genre_opts = _options(sorted(genres))

    if not films:
        body = '<div class="empty">No films yet. Run <code>filmlist pull &lt;year&gt;</code>.</div>'
    else:
        sections = []
        for fest in ordered_fests:
            cards = "\n".join(_render_card(f) for f in by_fest[fest])
            sections.append(
                f'<section class="fest" data-fest="{_esc(fest)}">'
                f'<h2>{_esc(fest)} <span class="count">{len(by_fest[fest])} films</span></h2>'
                f'<div class="bar"></div>'
                f'<div class="grid">{cards}</div>'
                "</section>"
            )
        body = "\n".join(sections)

    return PAGE_TEMPLATE.format(
        count=len(films),
        fest_count=len(by_fest),
        today=date.today().isoformat(),
        festival_opts=festival_opts,
        year_opts=year_opts,
        genre_opts=genre_opts,
        body=body,
    )


def write_html(films: Iterable[Film], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.write_text(render_html(films), encoding="utf-8")
    return out_path
