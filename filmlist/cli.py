"""Command-line interface for the film-festival database."""

from __future__ import annotations

import argparse
import sys

from .db import Database, DEFAULT_DB_PATH
from .fetch import FetchError, FESTIVAL_AWARDS, fetch_all_awards, fetch_award_winners
from .generate import write_html
from .models import Film, FESTIVALS


def cmd_add(args: argparse.Namespace) -> int:
    film = Film(
        title=args.title,
        year=args.year,
        festival=args.festival,
        director=args.director or "",
        country=args.country or "",
        genre=args.genre or "",
        section=args.section or "",
        award=args.award or "",
        synopsis=args.synopsis or "",
    )
    with Database(args.db) as db:
        film_id = db.add(film, source="manual")
    print(f"Added [{film_id}] {film.title} ({film.year}) — {film.festival}")
    print("Note: manually added films are excluded from the generated page "
          "unless you pass --include-manual to `generate`.")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    try:
        if args.festival:
            films = fetch_award_winners(args.festival, args.year)
        else:
            films = fetch_all_awards(args.year)
    except FetchError as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        return 1

    if not films:
        scope = args.festival or "any mapped festival"
        print(f"No {args.year} winners returned from Wikidata for {scope}.")
        return 0

    with Database(args.db) as db:
        db.add_many(films, merge=True, source="pull")
    scope = args.festival or "all mapped festivals"
    print(f"Pulled {len(films)} {args.year} award winner(s) for {scope} into {args.db}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    source = None if args.include_manual else "pull"
    with Database(args.db) as db:
        films = db.all(festival=args.festival, year=args.year, source=source)
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
    # By default the page shows only automatically pulled films.
    source = None if args.include_manual else "pull"
    with Database(args.db) as db:
        films = db.all(source=source)
    out = write_html(films, args.output)
    print(f"Wrote {len(films)} films to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="filmlist",
        description="Maintain a database of movies from major film festivals "
        "and generate a filterable HTML page.",
    )
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH})",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser(
        "pull",
        help="Fetch a year's festival award winners from Wikidata",
    )
    pp.add_argument(
        "year", type=int, help="The festival year to pull (one year per run)"
    )
    pp.add_argument(
        "--festival",
        choices=sorted(FESTIVAL_AWARDS),
        help="Limit to one festival (default: all mapped festivals)",
    )
    pp.set_defaults(func=cmd_pull)

    ap = sub.add_parser("add", help="Add a single film by hand (excluded from page)")
    ap.add_argument("title")
    ap.add_argument("year", type=int)
    ap.add_argument("festival", choices=FESTIVALS)
    ap.add_argument("--director")
    ap.add_argument("--country")
    ap.add_argument("--genre")
    ap.add_argument("--section")
    ap.add_argument("--award")
    ap.add_argument("--synopsis")
    ap.set_defaults(func=cmd_add)

    lp = sub.add_parser("list", help="List films")
    lp.add_argument("--festival", choices=FESTIVALS)
    lp.add_argument("--year", type=int)
    lp.add_argument(
        "--include-manual",
        action="store_true",
        help="Also list hand-added films (default: pulled films only)",
    )
    lp.set_defaults(func=cmd_list)

    dp = sub.add_parser("delete", help="Delete a film by id")
    dp.add_argument("id", type=int)
    dp.set_defaults(func=cmd_delete)

    gp = sub.add_parser("generate", help="Generate the HTML page")
    gp.add_argument(
        "-o", "--output", default="index.html", help="Output HTML file"
    )
    gp.add_argument(
        "--include-manual",
        action="store_true",
        help="Also include hand-added films (default: pulled films only)",
    )
    gp.set_defaults(func=cmd_generate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
