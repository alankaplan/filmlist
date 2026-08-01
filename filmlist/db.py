"""SQLite persistence for the film-festival database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .models import Film

DEFAULT_DB_PATH = Path("filmlist.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS films (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title    TEXT    NOT NULL,
    year     INTEGER NOT NULL,
    festival TEXT    NOT NULL,
    director TEXT    NOT NULL DEFAULT '',
    country  TEXT    NOT NULL DEFAULT '',
    genre    TEXT    NOT NULL DEFAULT '',
    section  TEXT    NOT NULL DEFAULT '',
    award    TEXT    NOT NULL DEFAULT '',
    synopsis TEXT    NOT NULL DEFAULT '',
    tags     TEXT    NOT NULL DEFAULT '',
    rt_score TEXT    NOT NULL DEFAULT '',
    -- Provenance: 'pull' = fetched by the automated pull system,
    -- 'manual' = entered by hand. The HTML output shows 'pull' only.
    source   TEXT    NOT NULL DEFAULT 'manual',
    UNIQUE(title, year, festival)
);
"""


class Database:
    """A thin, well-behaved wrapper around a SQLite film store."""

    # Columns added after the first release, with the DDL to add them to an
    # older database that predates them.
    _MIGRATIONS = {
        "genre": "ALTER TABLE films ADD COLUMN genre TEXT NOT NULL DEFAULT ''",
        "source": "ALTER TABLE films ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'",
        "tags": "ALTER TABLE films ADD COLUMN tags TEXT NOT NULL DEFAULT ''",
        "rt_score": "ALTER TABLE films ADD COLUMN rt_score TEXT NOT NULL DEFAULT ''",
    }

    def __init__(self, path: Path | str = DEFAULT_DB_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add any columns missing from a database created by an older
        version, so existing files keep working across upgrades."""
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(films)").fetchall()
        }
        for column, ddl in self._MIGRATIONS.items():
            if column not in existing:
                self.conn.execute(ddl)

    # -- context manager -------------------------------------------------
    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # -- writes ----------------------------------------------------------
    # Overwrite every field with the incoming values.
    _UPSERT_OVERWRITE = """
        director = excluded.director,
        country  = excluded.country,
        genre    = excluded.genre,
        section  = excluded.section,
        award    = excluded.award,
        synopsis = excluded.synopsis,
        tags     = excluded.tags,
        rt_score = excluded.rt_score,
        source   = excluded.source
    """

    # Fill only fields that are currently blank, preserving curated data.
    _UPSERT_MERGE = """
        director = CASE WHEN films.director = '' THEN excluded.director ELSE films.director END,
        country  = CASE WHEN films.country  = '' THEN excluded.country  ELSE films.country  END,
        genre    = CASE WHEN films.genre    = '' THEN excluded.genre    ELSE films.genre    END,
        section  = CASE WHEN films.section  = '' THEN excluded.section  ELSE films.section  END,
        award    = CASE WHEN films.award    = '' THEN excluded.award    ELSE films.award    END,
        synopsis = CASE WHEN films.synopsis = '' THEN excluded.synopsis ELSE films.synopsis END,
        tags     = CASE WHEN films.tags     = '' THEN excluded.tags     ELSE films.tags     END,
        rt_score = CASE WHEN films.rt_score = '' THEN excluded.rt_score ELSE films.rt_score END,
        source   = excluded.source
    """

    def add(self, film: Film, merge: bool = False, source: str = "manual") -> int:
        """Insert a film, returning its id. Existing (title, year, festival)
        rows are updated in place so re-running a pull is idempotent.

        ``source`` records provenance ('pull' or 'manual'). With
        ``merge=True`` only blank columns on the existing row are filled,
        so an automated fetch never overwrites hand-curated data."""
        set_clause = self._UPSERT_MERGE if merge else self._UPSERT_OVERWRITE
        params = film.to_dict()
        params["source"] = source
        cur = self.conn.execute(
            f"""
            INSERT INTO films (title, year, festival, director, country,
                               genre, section, award, synopsis, tags, rt_score,
                               source)
            VALUES (:title, :year, :festival, :director, :country,
                    :genre, :section, :award, :synopsis, :tags, :rt_score,
                    :source)
            ON CONFLICT(title, year, festival) DO UPDATE SET
            {set_clause}
            """,
            params,
        )
        self.conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self.conn.execute(
            "SELECT id FROM films WHERE title=? AND year=? AND festival=?",
            (film.title, film.year, film.festival),
        ).fetchone()
        return row["id"]

    def add_many(
        self, films: Iterable[Film], merge: bool = False, source: str = "manual"
    ) -> int:
        count = 0
        for film in films:
            self.add(film, merge=merge, source=source)
            count += 1
        return count

    def delete(self, film_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM films WHERE id = ?", (film_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def set_tags(self, film_id: int, tags: str) -> None:
        self.conn.execute(
            "UPDATE films SET tags = ? WHERE id = ?", (tags, film_id)
        )
        self.conn.commit()

    # -- reads -----------------------------------------------------------
    def _row_to_film(self, row: sqlite3.Row) -> Film:
        return Film(
            id=row["id"],
            title=row["title"],
            year=row["year"],
            festival=row["festival"],
            director=row["director"],
            country=row["country"],
            genre=row["genre"],
            section=row["section"],
            award=row["award"],
            synopsis=row["synopsis"],
            tags=row["tags"],
            rt_score=row["rt_score"],
        )

    def all(
        self,
        festival: Optional[str] = None,
        year: Optional[int] = None,
        source: Optional[str] = None,
    ) -> list[Film]:
        query = "SELECT * FROM films"
        clauses, params = [], []
        if festival:
            clauses.append("festival = ?")
            params.append(festival)
        if year:
            clauses.append("year = ?")
            params.append(year)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY year DESC, festival ASC, title ASC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_film(r) for r in rows]

    def get(self, film_id: int) -> Optional[Film]:
        row = self.conn.execute(
            "SELECT * FROM films WHERE id = ?", (film_id,)
        ).fetchone()
        return self._row_to_film(row) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS c FROM films").fetchone()["c"]
