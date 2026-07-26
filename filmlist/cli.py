"""Command-line interface for the film-festival database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .db import Database, DEFAULT_DB_PATH
from .generate import write_html
from .models import Film, FESTIVALS

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.json"


def _load_films_from_json(path: Path) -> list[Film]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Film(**item) for item in data]


def cmd_seed(args: argparse.Namespace) -> int:
    path = Path(args.file) if args.file else SEED_PATH
    if not path.exists():
        print(f"Seed file not found: {path}", file=sys.stderr)
        return 1
    films = _load_films_from_json(path)
    with Database(args.db) as db:
        n = db.add_many(films)
    print(f"Seeded {n} films from {path} into {args.db}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    film = Film(
        title=args.title,
        year=args.year,
        festival=args.festival,
        director=args.director or "",
        country=args.country or "",
        section=args.section or "",
        award=args.award or "",
        synopsis=args.synopsis or "",
    )
    with Database(args.db) as db:
        film_id = db.add(film)
    print(f"Added [{film_id}] {film.title} ({film.year}) — {film.festival}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        films = db.all(festival=args.festival, year=args.year)
    if not films:
        print("No films found.")
        return 0
    for f in films:
        award = f" — {f.award}" if f.award else ""
        print(f"[{f.id:>3}] {f.year}  {f.festival:<14} {f.title}{award}")
    print(f"\n{len(films)} film(s).")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        ok = db.delete(args.id)
    print(f"Deleted film {args.id}." if ok else f"No film with id {args.id}.")
    return 0 if ok else 1


def cmd_generate(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        films = db.all()
    out = write_html(films, args.output)
    print(f"Wrote {len(films)} films to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="filmlist",
        description="Maintain a database of movies from major film festivals "
        "and generate an HTML page.",
    )
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH})",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("seed", help="Load films from a JSON seed file")
    sp.add_argument("--file", help="Seed JSON file (default: bundled data/seed.json)")
    sp.set_defaults(func=cmd_seed)

    ap = sub.add_parser("add", help="Add a single film")
    ap.add_argument("title")
    ap.add_argument("year", type=int)
    ap.add_argument("festival", choices=FESTIVALS)
    ap.add_argument("--director")
    ap.add_argument("--country")
    ap.add_argument("--section")
    ap.add_argument("--award")
    ap.add_argument("--synopsis")
    ap.set_defaults(func=cmd_add)

    lp = sub.add_parser("list", help="List films")
    lp.add_argument("--festival", choices=FESTIVALS)
    lp.add_argument("--year", type=int)
    lp.set_defaults(func=cmd_list)

    dp = sub.add_parser("delete", help="Delete a film by id")
    dp.add_argument("id", type=int)
    dp.set_defaults(func=cmd_delete)

    gp = sub.add_parser("generate", help="Generate the HTML page")
    gp.add_argument(
        "-o", "--output", default="index.html", help="Output HTML file"
    )
    gp.set_defaults(func=cmd_generate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
