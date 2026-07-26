"""Render the film database to a single, self-contained HTML page."""

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
.controls {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 1.6rem; }}
.filter {{
  border: 1px solid var(--line); background: var(--chip); color: var(--text);
  padding: .4rem .85rem; border-radius: 999px; cursor: pointer; font-size: .88rem;
}}
.filter:hover {{ border-color: var(--accent); }}
.filter.active {{ background: var(--accent); color: #1a1204; border-color: var(--accent); font-weight: 600; }}
.fest {{ margin: 0 0 2.2rem; }}
.fest h2 {{
  font-size: 1.25rem; margin: 0 0 .2rem; display: flex; align-items: baseline; gap: .6rem;
}}
.fest h2 .count {{ font-size: .8rem; color: var(--muted); font-weight: 400; }}
.fest .bar {{ height: 2px; background: var(--accent); width: 44px; margin: 0 0 1rem; }}
.grid {{
  display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}}
.card {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem 1.1rem; transition: transform .12s ease, border-color .12s ease;
}}
.card:hover {{ transform: translateY(-2px); border-color: var(--accent); }}
.card .title {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 .15rem; }}
.card .meta {{ color: var(--muted); font-size: .85rem; margin: 0 0 .55rem; }}
.card .award {{
  display: inline-block; font-size: .78rem; color: var(--accent);
  border: 1px solid var(--accent); border-radius: 6px; padding: .1rem .45rem;
  margin: 0 0 .55rem;
}}
.card .synopsis {{ font-size: .9rem; color: #c7ccd6; margin: .2rem 0 0; }}
footer {{ color: var(--muted); text-align: center; padding: 2rem 1rem; font-size: .82rem; }}
.empty {{ color: var(--muted); padding: 3rem 0; text-align: center; }}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>Film Festival <span class="accent">Database</span></h1>
  <div class="sub">{count} films across {fest_count} major festivals &middot; generated {today}</div>
</div></header>
<main>
  <div class="controls" id="controls">
    <button class="filter active" data-fest="all">All</button>
    {filter_buttons}
  </div>
  {body}
</main>
<footer>Built with filmlist &middot; a database of movies from major film festivals</footer>
<script>
const buttons = document.querySelectorAll('.filter');
const sections = document.querySelectorAll('.fest');
buttons.forEach(btn => btn.addEventListener('click', () => {{
  buttons.forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const target = btn.dataset.fest;
  sections.forEach(sec => {{
    sec.style.display = (target === 'all' || sec.dataset.fest === target) ? '' : 'none';
  }});
}}));
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
    synopsis_html = (
        f'<p class="synopsis">{_esc(film.synopsis)}</p>' if film.synopsis else ""
    )
    return (
        '<div class="card">'
        f'<div class="title">{_esc(film.title)}</div>'
        f'<div class="meta">{meta}</div>'
        f"{award_html}"
        f"{synopsis_html}"
        "</div>"
    )


def render_html(films: Iterable[Film]) -> str:
    """Return a complete HTML document for the given films."""
    films = list(films)
    by_fest: dict[str, list[Film]] = defaultdict(list)
    for film in films:
        by_fest[film.festival].append(film)

    ordered_fests = sorted(by_fest, key=lambda f: (-len(by_fest[f]), f))

    filter_buttons = "\n    ".join(
        f'<button class="filter" data-fest="{_esc(f)}">{_esc(f)} '
        f'({len(by_fest[f])})</button>'
        for f in ordered_fests
    )

    if not films:
        body = '<div class="empty">No films yet. Add some or run the seed.</div>'
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
        filter_buttons=filter_buttons,
        body=body,
    )


def write_html(films: Iterable[Film], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.write_text(render_html(films), encoding="utf-8")
    return out_path
