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
from filmlist import tmdb
from filmlist.generate import render_html
from filmlist.models import Film
from filmlist.tagging import AGE_5, AGE_12, UNRATED, age_tags


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


def test_tag_list_property():
    assert make_film(tags="OK for 12, Cannes pick").tag_list == ["OK for 12", "Cannes pick"]
    assert make_film(tags="").tag_list == []


# --- tagging: no certification -> Unrated ---------------------------------
def test_age_tags_unrated_without_certification():
    # Genre alone never grants a positive tag, whatever the genre.
    assert age_tags(["Animation"]) == [UNRATED]
    assert age_tags(["Drama"]) == [UNRATED]          # the "Dreams" case
    assert age_tags(["Horror"]) == [UNRATED]
    assert age_tags([]) == [UNRATED]
    # Even mature keywords can't produce a positive tag with no certification.
    assert age_tags(["Drama"], keywords=["nudity"]) == [UNRATED]


# --- tagging: certification-driven ----------------------------------------
def test_age_tags_from_certification():
    assert age_tags(certification="G") == [AGE_5, AGE_12]
    assert age_tags(certification="U") == [AGE_5, AGE_12]
    assert age_tags(certification="PG") == [AGE_12]        # not for 5
    assert age_tags(certification="12A") == [AGE_12]
    assert age_tags(certification="PG-13") == []           # 13+, not for 12
    assert age_tags(certification="R") == []
    assert age_tags(certification="16") == []              # numeric cert


def test_certification_overrides_genre():
    # A kid genre with an adult certification is not marked kid-friendly.
    assert age_tags(["Animation"], certification="R") == []


def test_keywords_only_tighten_a_certification():
    # A G rating with a mature keyword loses the "OK for 5" tag.
    assert age_tags(certification="G", keywords=["nudity"]) == [AGE_12]
    # A hard keyword removes both tags even on a G rating.
    assert age_tags(certification="G", keywords=["graphic violence"]) == []


# --- tmdb client ----------------------------------------------------------
def _tmdb_fetcher(routes):
    """Build a fake fetcher that returns canned JSON based on the URL."""
    def fetch(url, params):
        for needle, payload in routes.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected url {url}")
    return fetch


def test_tmdb_certification_prefers_us_then_gb():
    payload = {"results": [
        {"iso_3166_1": "GB", "release_dates": [{"certification": "15"}]},
        {"iso_3166_1": "US", "release_dates": [{"certification": ""}, {"certification": "R"}]},
    ]}
    fetch = _tmdb_fetcher({"release_dates": payload})
    assert tmdb.certification("42", "key", fetch) == ("US", "R")


def test_tmdb_certification_falls_back_to_any_country():
    payload = {"results": [{"iso_3166_1": "FR", "release_dates": [{"certification": "12"}]}]}
    fetch = _tmdb_fetcher({"release_dates": payload})
    assert tmdb.certification("42", "key", fetch) == ("FR", "12")


def test_tmdb_keywords_lowercased():
    payload = {"keywords": [{"id": 1, "name": "Nudity"}, {"id": 2, "name": "Drug Abuse"}]}
    fetch = _tmdb_fetcher({"keywords": payload})
    assert tmdb.keywords("42", "key", fetch) == ["nudity", "drug abuse"]


def test_tmdb_resolve_id_direct_via_imdb_and_search():
    routes = {
        "/find/": {"movie_results": [{"id": 999}]},
        "/search/movie": {"results": [
            {"id": 777, "title": "Dreams", "release_date": "2025-02-14"},
        ]},
    }
    fetch = _tmdb_fetcher(routes)
    assert tmdb.resolve_id("123", "", "key", fetch) == "123"                 # direct
    assert tmdb.resolve_id("", "tt0111161", "key", fetch) == "999"          # /find
    # No linked ids -> title+year search fallback.
    assert tmdb.resolve_id("", "", "key", fetch, "Dreams", 2025) == "777"


def test_tmdb_search_requires_title_and_year_match():
    routes = {"/search/movie": {"results": [
        {"id": 1, "title": "Dreams", "release_date": "2019-01-01"},   # wrong year
        {"id": 2, "title": "Other Film", "release_date": "2025-01-01"},  # wrong title
        {"id": 3, "title": "Dreams", "release_date": "2024-11-01"},   # ok (±1 year)
    ]}}
    fetch = _tmdb_fetcher(routes)
    assert tmdb.search_id("Dreams", 2025, "key", fetch) == "3"
    assert tmdb.search_id("Nonexistent", 2025, "key", fetch) is None


def test_tmdb_content_signals_combines_calls():
    routes = {
        "release_dates": {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "PG-13"}]}]},
        "keywords": {"keywords": [{"name": "Violence"}]},
    }
    rating, kws = tmdb.content_signals("55", "", "key", _tmdb_fetcher(routes))
    assert rating == "PG-13"
    assert kws == ["violence"]


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


def test_retag_strips_obsolete_age_tags_and_keeps_custom(tmp_path):
    from filmlist import cli
    dbp = tmp_path / "t.db"
    with Database(dbp) as db:
        db.add(make_film(title="X", genre="Animation", tags="16+, favorite"),
               source="pull")
    cli.main(["--db", str(dbp), "retag"])
    with Database(dbp) as db:
        got = db.all()[0]
    assert "16+" not in got.tag_list          # obsolete age tag removed
    assert "favorite" in got.tag_list         # custom tag preserved
    # Offline retag can't fetch certifications, so the film is Unrated.
    assert UNRATED in got.tag_list
    assert AGE_5 not in got.tag_list


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
                "tmdb": {"value": "12345"},
                "imdb": {"value": "tt0000001"},
            },
            {  # no title -> skipped
                "award": {"value": "Grand Prix"},
                "filmLabel": {"value": ""},
            },
        ]
    }
}


def test_parse_results_builds_films_titles_and_ids():
    films, titles, ext = _parse_results(SPARQL_SAMPLE, "Cannes", 2024)
    assert [f.title for f in films] == ["Anora"]
    assert films[0].genre == "Comedy, Drama"
    assert films[0].award == "Palme d'Or"
    assert films[0].year == 2024
    assert titles == {0: "Anora (film)"}
    assert ext == {0: ("12345", "tt0000001")}


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

    films = fetch_award_winners("Cannes", 2024, fetcher=fake_fetch, with_tmdb=False)
    assert len(films) == 1
    assert films[0].synopsis.startswith("Anora is a 2024 film")
    # Without a certification (TMDB off), the film is Unrated, never a guess.
    assert films[0].tags == UNRATED


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
def test_render_html_has_four_multiselect_facets_and_data():
    films = [
        make_film(title="Anora", festival="Cannes", year=2024,
                  genre="Comedy, Drama", award="Palme d'Or", tags="OK for 12"),
        make_film(title="Flow", festival="Sundance", year=2024, genre="Animation",
                  tags="OK for 5, OK for 12"),
        make_film(title="Dreams", festival="Berlin", year=2025, genre="Drama",
                  tags="Unrated"),
    ]
    html = render_html(films)
    # Each filter is a checkbox dropdown for its dimension.
    for dim in ("festival", "year", "genre", "tags"):
        assert f'<details class="dd" data-dim="{dim}">' in html
    # Item data attributes drive the additive client-side filter.
    assert 'data-genre="Comedy|Drama"' in html
    assert 'data-tags="OK for 12"' in html
    assert 'data-tags="OK for 5|OK for 12"' in html
    assert 'data-tags="Unrated"' in html
    assert 'data-year="2024"' in html
    # Dropdown options are checkboxes populated from the data.
    assert '<input type="checkbox" value="Comedy"><span>Comedy</span>' in html
    assert '<input type="checkbox" value="OK for 5"><span>OK for 5</span>' in html
    assert '<input type="checkbox" value="Unrated"><span>Unrated</span>' in html
    # "Unrated" is a neutral pill in the item body, not a green age tag.
    assert '<span class="g">Unrated</span>' in html


def test_render_html_escapes():
    films = [make_film(title="<script>evil</script>")]
    html = render_html(films)
    assert "<script>evil</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_empty():
    html = render_html([])
    assert "No films yet" in html
