import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def temp_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKLOG_DATA_DIR", str(tmp_path))
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]
    from backend import db as db_module
    db_module.init_db()
    yield tmp_path


def _insert(conn, **kwargs):
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" for _ in kwargs)
    conn.execute(f"INSERT INTO games ({cols}) VALUES ({placeholders})", list(kwargs.values()))


def test_ownership_only_reported_for_backlog(temp_data_dir):
    """Un jeu fini n'a plus de notion de 'possession' dans les stats : par
    définition on l'a possédé pour y jouer, ce suivi n'apporte rien."""
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="Fini possédé", status="completed", available=1, rating=5)
    _insert(conn, title="Backlog possédé", status="backlog", available=1)
    _insert(conn, title="Backlog pas possédé", status="backlog", available=0)
    conn.commit()
    conn.close()

    stats = compute_stats()
    assert "completed" not in stats["ownership"]
    assert stats["ownership"]["backlog"]["owned"] == 1
    assert stats["ownership"]["backlog"]["not_owned"] == 1


def test_best_and_worst_rated_game(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="Excellent", status="completed", rating=5)
    _insert(conn, title="Mediocre", status="completed", rating=1)
    _insert(conn, title="Moyen", status="completed", rating=3)
    conn.commit()
    conn.close()

    stats = compute_stats()
    assert stats["best_rated_game"]["title"] == "Excellent"
    assert stats["best_rated_game"]["rating"] == 5
    assert stats["worst_rated_game"]["title"] == "Mediocre"
    assert stats["worst_rated_game"]["rating"] == 1


def test_best_rated_tie_break_is_random_among_ties(temp_data_dir, monkeypatch):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="Jeu A", status="completed", rating=5)
    _insert(conn, title="Jeu B", status="completed", rating=5)
    conn.commit()
    conn.close()

    # Force le tirage aléatoire à toujours choisir le 2e élément de la liste
    monkeypatch.setattr("backend.stats.random.choice", lambda seq: seq[-1])
    stats = compute_stats()
    assert stats["best_rated_game"]["title"] in ("Jeu A", "Jeu B")


def test_rating_and_month_charts_filterable_by_year_others_stay_global(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="Jeu 2024", status="completed", rating=4,
            year_finished=2024, month_finished="Mars")
    _insert(conn, title="Jeu 2025", status="completed", rating=2,
            year_finished=2025, month_finished="Juin")
    conn.commit()
    conn.close()

    stats_all = compute_stats()
    assert stats_all["nb_completed"] == 2  # vue globale non filtrée
    assert len(stats_all["rating_histogram"]) == 10

    stats_2024 = compute_stats(year=2024)
    assert stats_2024["nb_completed"] == 2  # le total reste global...
    ratings_2024 = {r["rating"]: r["nb"] for r in stats_2024["rating_histogram"]}
    assert ratings_2024[4] == 1
    assert ratings_2024[2] == 0  # ...mais la répartition des notes est bien filtrée
    months_2024 = [m["month"] for m in stats_2024["by_month"]]
    assert months_2024 == ["Mars"]


def test_year_review_builds_expected_highlights(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import build_year_review

    conn = get_conn()
    _insert(conn, title="Le mieux noté", status="completed", rating=5,
            year_finished=2025, hours_played=10, review="Court avis")
    _insert(conn, title="Le plus joué", status="completed", rating=3,
            year_finished=2025, hours_played=80, review="x" * 300)
    _insert(conn, title="Autre année", status="completed", rating=5,
            year_finished=2020, hours_played=999)
    conn.commit()
    conn.close()

    review = build_year_review(2025)
    assert review["nb_completed"] == 2
    assert review["best_rated_game"]["title"] == "Le mieux noté"
    assert review["most_played_game"]["title"] == "Le plus joué"
    assert review["longest_review_game"]["title"] == "Le plus joué"
    assert len(review["longest_review_game"]["review_excerpt"]) <= 220


def test_year_review_returns_none_for_year_with_no_games(temp_data_dir):
    from backend.stats import build_year_review
    assert build_year_review(1999) is None


def test_list_review_years_sorted_descending(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import list_review_years

    conn = get_conn()
    _insert(conn, title="A", status="completed", year_finished=2022)
    _insert(conn, title="B", status="completed", year_finished=2025)
    _insert(conn, title="C", status="completed", year_finished=2023)
    conn.commit()
    conn.close()

    assert list_review_years() == [2025, 2023, 2022]


# ------------------------------------------------------------- Pace (hours/month, backlog projection)

def test_pace_avg_hours_per_month_uses_distinct_active_months(temp_data_dir):
    """Two games finished in the same (year, month) count as one active
    month, not two — the average shouldn't be diluted by clustering."""
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="A", status="completed", year_finished=2024, month_finished="Mars", hours_played=10)
    _insert(conn, title="B", status="completed", year_finished=2024, month_finished="Mars", hours_played=10)
    _insert(conn, title="C", status="completed", year_finished=2024, month_finished="Avril", hours_played=20)
    conn.commit()
    conn.close()

    stats = compute_stats()
    # total 40h across 2 distinct active months (Mars, Avril) = 20h/month
    assert stats["pace"]["avg_hours_per_month"] == 20.0


def test_pace_months_to_clear_backlog(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="A", status="completed", year_finished=2024, month_finished="Mars", hours_played=10)
    _insert(conn, title="B", status="backlog", hours_estimated=25)
    conn.commit()
    conn.close()

    stats = compute_stats()
    assert stats["pace"]["avg_hours_per_month"] == 10.0
    assert stats["pace"]["months_to_clear_backlog"] == 2.5


def test_pace_is_none_when_no_completed_games_have_dates(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="A", status="backlog", hours_estimated=10)
    conn.commit()
    conn.close()

    stats = compute_stats()
    assert stats["pace"]["avg_hours_per_month"] is None
    assert stats["pace"]["months_to_clear_backlog"] is None


def test_dlc_stats_include_backlog_count(temp_data_dir):
    from backend.db import get_conn
    from backend.stats import compute_stats

    conn = get_conn()
    _insert(conn, title="A", status="completed", dlc=1)
    _insert(conn, title="B", status="completed", dlc=0)
    _insert(conn, title="C", status="backlog", dlc=1)
    conn.commit()
    conn.close()

    stats = compute_stats()
    assert stats["dlc"]["nb_dlc"] == 1
    assert stats["dlc"]["nb_base_games"] == 1
    assert stats["dlc"]["nb_dlc_backlog"] == 1
