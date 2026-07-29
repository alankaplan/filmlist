"""Render the film database to a single, self-contained HTML page.

The page is a flat list of films with four additive, multi-select filters —
festival, year, genre, and tag. Within a filter, selecting several values
widens the results (OR); across filters they narrow (AND)."""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Iterable

from .models import Film
from .tagging import AGE_TAGS

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
.facet {{ margin: 0 0 .8rem; }}
.facet:last-of-type {{ margin-bottom: 0; }}
.facet .flabel {{
  font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 0 0 .4rem;
}}
.chips {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.chip {{
  border: 1px solid var(--line); background: var(--chip); color: var(--text);
  padding: .28rem .7rem; border-radius: 999px; cursor: pointer; font-size: .82rem;
}}
.chip:hover {{ border-color: var(--accent); }}
.chip.active {{ background: var(--accent); color: #1a1204; border-color: var(--accent); font-weight: 600; }}
.chips[data-dim="tags"] .chip.active {{ background: var(--age); border-color: var(--age); color: #06231a; }}
.toolbar {{ display: flex; align-items: center; gap: 1rem; margin-top: .9rem; padding-top: .8rem; border-top: 1px solid var(--line); }}
#count {{ color: var(--muted); font-size: .9rem; }}
#clear {{
  margin-left: auto; background: none; border: 1px solid var(--line); color: var(--muted);
  border-radius: 8px; padding: .3rem .7rem; font-size: .8rem; cursor: pointer;
}}
#clear:hover {{ border-color: var(--accent); color: var(--text); }}
.list {{ display: flex; flex-direction: column; gap: .7rem; }}
.item {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: .95rem 1.1rem; transition: border-color .12s ease;
}}
.item:hover {{ border-color: var(--accent); }}
.item .head {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem; }}
.item .title {{ font-size: 1.1rem; font-weight: 600; }}
.item .award {{
  font-size: .75rem; color: var(--accent);
  border: 1px solid var(--accent); border-radius: 6px; padding: .05rem .45rem;
}}
.item .meta {{ color: var(--muted); font-size: .86rem; margin: .25rem 0 0; }}
.item .meta .fest {{ color: var(--accent); font-weight: 600; }}
.taglist {{ display: flex; flex-wrap: wrap; gap: .3rem; margin: .5rem 0 0; }}
.taglist .g {{
  font-size: .72rem; color: var(--muted); background: var(--chip);
  border: 1px solid var(--line); border-radius: 999px; padding: .08rem .5rem;
}}
.taglist .age {{ color: #062018; background: var(--age); border-color: var(--age); font-weight: 600; }}
.item .synopsis {{ font-size: .9rem; color: #c7ccd6; margin: .5rem 0 0; }}
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
    {facets}
    <div class="toolbar">
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

function itemValues(item, dim) {{
  if (dim === 'festival') return [item.dataset.festival];
  if (dim === 'year') return [item.dataset.year];
  return (item.dataset[dim] || '').split('|').filter(Boolean);
}}

function apply() {{
  let visible = 0;
  items.forEach(item => {{
    const ok = DIMS.every(dim => {{
      const sel = active[dim];
      return sel.size === 0 || itemValues(item, dim).some(v => sel.has(v));
    }});
    item.style.display = ok ? '' : 'none';
    if (ok) visible++;
  }});
  countEl.textContent = visible + ' of ' + items.length + ' films';
  noResults.style.display = visible ? 'none' : '';
}}

document.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {{
  const dim = chip.parentElement.dataset.dim;
  const val = chip.dataset.val;
  if (active[dim].has(val)) {{ active[dim].delete(val); chip.classList.remove('active'); }}
  else {{ active[dim].add(val); chip.classList.add('active'); }}
  apply();
}}));

document.getElementById('clear').addEventListener('click', () => {{
  DIMS.forEach(d => active[d].clear());
  document.querySelectorAll('.chip.active').forEach(c => c.classList.remove('active'));
  apply();
}});

apply();
</script>
</body>
</html>
"""


def _esc(text: str) -> str:
    return html.escape(text or "")


def _facet(label: str, dim: str, values: Iterable) -> str:
    chips = "".join(
        f'<button class="chip" data-val="{_esc(str(v))}">{_esc(str(v))}</button>'
        for v in values
    )
    return (
        f'<div class="facet"><div class="flabel">{_esc(label)}</div>'
        f'<div class="chips" data-dim="{dim}">{chips}</div></div>'
    )


def _render_item(film: Film) -> str:
    award_html = f'<span class="award">🏆 {_esc(film.award)}</span>' if film.award else ""

    # Festival lives in the film's info now (no per-festival sections).
    meta_bits = [f'<span class="fest">{_esc(film.festival)}</span>', str(film.year)]
    if film.director:
        meta_bits.append(_esc(film.director))
    if film.country:
        meta_bits.append(_esc(film.country))
    if film.section:
        meta_bits.append(_esc(film.section))
    meta = " &middot; ".join(meta_bits)

    pills = [f'<span class="g">{_esc(g)}</span>' for g in film.genres]
    for t in film.tag_list:
        cls = "g age" if t in AGE_TAGS else "g"
        pills.append(f'<span class="{cls}">{_esc(t)}</span>')
    pills_html = f'<div class="taglist">{"".join(pills)}</div>' if pills else ""

    synopsis_html = (
        f'<p class="synopsis">{_esc(film.synopsis)}</p>' if film.synopsis else ""
    )
    data_genre = _esc("|".join(film.genres))
    data_tags = _esc("|".join(film.tag_list))
    return (
        f'<div class="item" data-festival="{_esc(film.festival)}" '
        f'data-year="{film.year}" data-genre="{data_genre}" data-tags="{data_tags}">'
        f'<div class="head"><span class="title">{_esc(film.title)}</span>{award_html}</div>'
        f'<div class="meta">{meta}</div>'
        f"{pills_html}"
        f"{synopsis_html}"
        "</div>"
    )


def _sort_tags(tags: set[str]) -> list[str]:
    """Age tags first (in age order), then any other tags alphabetically."""
    age = [t for t in AGE_TAGS if t in tags]
    other = sorted(t for t in tags if t not in AGE_TAGS)
    return age + other


def render_html(films: Iterable[Film]) -> str:
    """Return a complete HTML document for the given films."""
    films = list(films)
    festivals: list[str] = []
    genres: set[str] = set()
    tags: set[str] = set()
    years: set[int] = set()
    for film in films:
        if film.festival not in festivals:
            festivals.append(film.festival)
        years.add(film.year)
        genres.update(film.genres)
        tags.update(film.tag_list)

    facets = "\n    ".join([
        _facet("Festival", "festival", sorted(festivals)),
        _facet("Year", "year", sorted(years, reverse=True)),
        _facet("Genre", "genre", sorted(genres)),
        _facet("Tags", "tags", _sort_tags(tags)),
    ])

    if not films:
        body = '<div class="empty">No films yet. Run <code>filmlist pull &lt;year&gt;</code>.</div>'
    else:
        rows = "\n".join(_render_item(f) for f in films)
        body = f'<div class="list">{rows}</div>'

    return PAGE_TEMPLATE.format(
        count=len(films),
        fest_count=len(festivals),
        today=date.today().isoformat(),
        facets=facets,
        body=body,
    )


def write_html(films: Iterable[Film], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.write_text(render_html(films), encoding="utf-8")
    return out_path
