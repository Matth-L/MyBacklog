import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.dateutils import month_year_from_iso


def test_valid_date():
    assert month_year_from_iso("2024-03-15") == ("Mars", 2024)


def test_january_and_december_boundaries():
    assert month_year_from_iso("2025-01-01") == ("Janvier", 2025)
    assert month_year_from_iso("2025-12-31") == ("Décembre", 2025)


def test_none_or_empty_returns_none():
    assert month_year_from_iso(None) == (None, None)
    assert month_year_from_iso("") == (None, None)


def test_invalid_date_returns_none():
    assert month_year_from_iso("not-a-date") == (None, None)
    assert month_year_from_iso("2024-13-40") == (None, None)
