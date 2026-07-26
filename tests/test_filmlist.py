"""Tests for the filmlist app."""

import json
from pathlib import Path

import pytest

from filmlist.db import Database
from filmlist.fetch import _parse_results, build_query, fetch_award_winners
from filmlist.generate import render_html
from filmlist.models import Film


def make_film(**kw) -> Film:
    base = dict(title="Test Film", year=2023, festival="Cannes")
    base.update(kw)
    return Film(**base)


def test_film_validation_rejects_unknown_festival():
    with pytest.raises(ValueError):
        make_film(festival="Oscars")


def test_film_validation_rejects_empty_title():
    with pytest.raises(ValueError):
        make_film(title="   ")


def test_film_validation_rejects_bad_year():
    with pytest.raises(ValueError):
        make_film(year=1500)


def test_add_and_get(tmp_path):
    with Database(tmp_path / "t.db") as db:
        fid = db.add(make_film(title="Parasite", festival="Cannes"))
        got = db.get(fid)
        assert got is not None
        assert got.title == "Parasite"
        assert db.count() == 1


def test_add_is_idempotent(tmp_path):
    with Database(tmp_path / "t.db") as db:
        f1 = db.add(make_film(title="X", award=""))
        f2 = db.add(make_film(title="X", award="Palme d'Or"))
        assert f1 == f2
        assert db.count() == 1
        assert db.get(f1).award == "Palme d'Or"


def test_filtering(tmp_path):
    with Database(tmp_path / "t.db") as db:
        db.add(make_film(title="A", festival="Cannes", year=2022))
        db.add(make_film(title="B", festival="Venice", year=2023))
        assert len(db.all()) == 2
        assert len(db.all(festival="Cannes")) == 1
        assert len(db.all(year=2023)) == 1


def test_delete(tmp_path):
    with Database(tmp_path / "t.db") as db:
        fid = db.add(make_film())
        assert db.delete(fid) is True
        assert db.delete(fid) is False
        assert db.count() == 0


def test_ordering_newest_first(tmp_path):
    with Database(tmp_path / "t.db") as db:
        db.add(make_film(title="Old", year=2010))
        db.add(make_film(title="New", year=2024))
        titles = [f.title for f in db.all()]
        assert titles[0] == "New"


def test_render_html_contains_films():
    films = [
        make_film(title="Parasite", festival="Cannes", award="Palme d'Or"),
        make_film(title="Joker", festival="Venice", award="Golden Lion"),
    ]
    html = render_html(films)
    assert "<!doctype html>" in html
    assert "Parasite" in html
    assert "Palme d&#x27;Or" in html or "Palme d'Or" in html
    assert 'data-fest="Cannes"' in html
    assert 'data-fest="Venice"' in html


def test_render_html_escapes():
    films = [make_film(title="<script>evil</script>")]
    html = render_html(films)
    assert "<script>evil</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_empty():
    html = render_html([])
    assert "No films yet" in html


def _binding(title, year, directors="", countries=""):
    b = {"filmLabel": {"value": title}, "year": {"value": str(year)}}
    if directors:
        b["directors"] = {"value": directors}
    if countries:
        b["countries"] = {"value": countries}
    return b


SAMPLE_SPARQL = {
    "results": {
        "bindings": [
            _binding("Anora", 2024, "Sean Baker", "United States"),
            _binding("Parasite", 2019, "Bong Joon-ho", "South Korea"),
            _binding("", 2020),          # missing title -> skipped
            _binding("No Year Film", ""),  # missing year -> skipped
        ]
    }
}


def test_build_query_includes_label_and_since():
    q = build_query("Palme d'Or", since=2020)
    assert '"Palme d\'Or"@en' in q
    assert "FILTER(?year >= 2020)" in q


def test_parse_results_skips_incomplete_rows():
    films = _parse_results(SAMPLE_SPARQL, "Cannes", "Palme d'Or")
    titles = [f.title for f in films]
    assert titles == ["Anora", "Parasite"]
    assert films[0].festival == "Cannes"
    assert films[0].award == "Palme d'Or"
    assert films[0].director == "Sean Baker"


def test_fetch_award_winners_with_injected_fetcher():
    def fake_fetch(endpoint, params):
        assert "query" in params
        return SAMPLE_SPARQL

    films = fetch_award_winners("Cannes", fetcher=fake_fetch)
    assert {f.title for f in films} == {"Anora", "Parasite"}


def test_merge_preserves_curated_fields(tmp_path):
    with Database(tmp_path / "t.db") as db:
        # Curated row with a hand-written synopsis and section.
        db.add(make_film(title="Anora", year=2024,
                         synopsis="Hand-written.", section="Competition"))
        # Fetched row (merge) has a director but blank synopsis/section.
        fetched = Film(title="Anora", year=2024, festival="Cannes",
                       director="Sean Baker", country="USA", award="Palme d'Or")
        db.add(fetched, merge=True)
        got = db.all()[0]
        assert got.synopsis == "Hand-written."   # preserved
        assert got.section == "Competition"       # preserved
        assert got.director == "Sean Baker"       # filled from fetch
        assert got.award == "Palme d'Or"          # filled from fetch


def test_seed_file_is_valid():
    seed = Path(__file__).resolve().parent.parent / "data" / "seed.json"
    data = json.loads(seed.read_text(encoding="utf-8"))
    assert len(data) > 0
    # Every entry must construct a valid Film.
    for item in data:
        Film(**item)
