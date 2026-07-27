"""Tests for the filmlist app."""

import pytest

from filmlist.db import Database
from filmlist.fetch import (
    FESTIVAL_AWARDS,
    _parse_results,
    _title_from_article,
    build_query,
    fetch_award_winners,
    fetch_summaries,
)
from filmlist.generate import render_html
from filmlist.models import Film


def make_film(**kw) -> Film:
    base = dict(title="Test Film", year=2023, festival="Cannes")
    base.update(kw)
    return Film(**base)


# --- models ---------------------------------------------------------------
def test_film_validation_rejects_unknown_festival():
    with pytest.raises(ValueError):
        make_film(festival="Oscars")


def test_film_validation_rejects_empty_title():
    with pytest.raises(ValueError):
        make_film(title="   ")


def test_film_validation_rejects_bad_year():
    with pytest.raises(ValueError):
        make_film(year=1500)


def test_sxsw_is_a_valid_festival():
    f = make_film(festival="SXSW")
    assert f.festival == "SXSW"


def test_genres_property_splits_and_trims():
    f = make_film(genre="Drama,  Thriller , Comedy")
    assert f.genres == ["Drama", "Thriller", "Comedy"]
    assert make_film(genre="").genres == []


# --- database -------------------------------------------------------------
def test_add_and_get(tmp_path):
    with Database(tmp_path / "t.db") as db:
        fid = db.add(make_film(title="Parasite"), source="pull")
        got = db.get(fid)
        assert got is not None
        assert got.title == "Parasite"
        assert db.count() == 1


def test_source_filter(tmp_path):
    with Database(tmp_path / "t.db") as db:
        db.add(make_film(title="Pulled"), source="pull")
        db.add(make_film(title="Manual", year=2022), source="manual")
        assert len(db.all()) == 2
        assert [f.title for f in db.all(source="pull")] == ["Pulled"]
        assert [f.title for f in db.all(source="manual")] == ["Manual"]


def test_merge_preserves_curated_fields(tmp_path):
    with Database(tmp_path / "t.db") as db:
        db.add(make_film(title="Anora", year=2024,
                         synopsis="Hand-written.", section="Competition"),
               source="manual")
        fetched = Film(title="Anora", year=2024, festival="Cannes",
                       director="Sean Baker", genre="Comedy", award="Palme d'Or")
        db.add(fetched, merge=True, source="pull")
        got = db.all()[0]
        assert got.synopsis == "Hand-written."   # preserved
        assert got.section == "Competition"       # preserved
        assert got.director == "Sean Baker"       # filled
        assert got.genre == "Comedy"              # filled


def test_migrates_legacy_schema(tmp_path):
    import sqlite3
    # A database created before the genre/source columns existed.
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, year INTEGER NOT NULL, festival TEXT NOT NULL,
            director TEXT DEFAULT '', country TEXT DEFAULT '',
            section TEXT DEFAULT '', award TEXT DEFAULT '', synopsis TEXT DEFAULT '',
            UNIQUE(title, year, festival)
        );
        INSERT INTO films (title, year, festival) VALUES ('Old Film', 2015, 'Cannes');
        """
    )
    con.commit()
    con.close()

    # Opening it should add the missing columns and remain usable.
    with Database(path) as db:
        assert db.count() == 1
        db.add(make_film(title="New Film", genre="Drama"), source="pull")
        got = [f for f in db.all() if f.title == "New Film"][0]
        assert got.genre == "Drama"
        # The legacy row defaults to the 'manual' source, so it stays off the page.
        assert db.all(source="pull") == [f for f in db.all() if f.title == "New Film"]


def test_delete(tmp_path):
    with Database(tmp_path / "t.db") as db:
        fid = db.add(make_film())
        assert db.delete(fid) is True
        assert db.delete(fid) is False
        assert db.count() == 0


# --- fetch ----------------------------------------------------------------
def test_every_festival_has_awards():
    for fest, awards in FESTIVAL_AWARDS.items():
        assert awards, f"{fest} has no awards mapped"


def test_sundance_and_sxsw_are_mapped():
    assert "Sundance" in FESTIVAL_AWARDS
    assert "SXSW" in FESTIVAL_AWARDS


def test_build_query_single_year_and_labels():
    q = build_query(["Palme d'Or", "Grand Prix"], year=2023)
    assert "FILTER(?year = 2023)" in q
    assert '"Palme d\'Or"' in q
    assert "wdt:P136" in q          # genre
    assert "schema:about ?film" in q  # wikipedia article


def test_title_from_article():
    url = "https://en.wikipedia.org/wiki/Anatomy_of_a_Fall"
    assert _title_from_article(url) == "Anatomy of a Fall"
    assert _title_from_article("") == ""


SPARQL_SAMPLE = {
    "results": {
        "bindings": [
            {
                "award": {"value": "Palme d'Or"},
                "filmLabel": {"value": "Anora"},
                "directors": {"value": "Sean Baker"},
                "countries": {"value": "United States"},
                "genres": {"value": "Comedy, Drama"},
                "description": {"value": "2024 film"},
                "article": {"value": "https://en.wikipedia.org/wiki/Anora_(film)"},
            },
            {  # no title -> skipped
                "award": {"value": "Grand Prix"},
                "filmLabel": {"value": ""},
            },
        ]
    }
}


def test_parse_results_builds_films_and_titles():
    films, titles = _parse_results(SPARQL_SAMPLE, "Cannes", 2024)
    assert [f.title for f in films] == ["Anora"]
    assert films[0].genre == "Comedy, Drama"
    assert films[0].award == "Palme d'Or"
    assert films[0].year == 2024
    assert titles == {0: "Anora (film)"}


def test_fetch_award_winners_enriches_with_summary():
    wiki_sample = {
        "query": {
            "pages": {
                "1": {"title": "Anora (film)", "extract": "Anora is a 2024 film about..."}
            }
        }
    }

    def fake_fetch(endpoint, params):
        return wiki_sample if "titles" in params else SPARQL_SAMPLE

    films = fetch_award_winners("Cannes", 2024, fetcher=fake_fetch)
    assert len(films) == 1
    assert films[0].synopsis.startswith("Anora is a 2024 film")


def test_fetch_summaries_resolves_redirects():
    sample = {
        "query": {
            "redirects": [{"from": "Old Title", "to": "New Title"}],
            "pages": {"1": {"title": "New Title", "extract": "Extract text."}},
        }
    }
    out = fetch_summaries(["Old Title"], fetcher=lambda e, p: sample)
    assert out["Old Title"] == "Extract text."


# --- html rendering -------------------------------------------------------
def test_render_html_has_three_filters_and_genre_data():
    films = [
        make_film(title="Anora", festival="Cannes", year=2024,
                  genre="Comedy, Drama", award="Palme d'Or"),
        make_film(title="Joker", festival="Venice", year=2019, genre="Thriller"),
    ]
    html = render_html(films)
    assert 'id="f-festival"' in html
    assert 'id="f-year"' in html
    assert 'id="f-genre"' in html
    assert 'data-genre="Comedy|Drama"' in html
    assert 'data-year="2024"' in html
    # Genre and year options are populated from the data.
    assert "<option value=\"Comedy\">Comedy</option>" in html
    assert "<option value=\"2024\">2024</option>" in html


def test_render_html_escapes():
    films = [make_film(title="<script>evil</script>")]
    html = render_html(films)
    assert "<script>evil</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_empty():
    html = render_html([])
    assert "No films yet" in html
