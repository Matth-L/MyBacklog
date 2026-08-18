import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.dateutils import (
    month_year_from_iso,
    month_name_to_number,
    month_number_to_name,
    MONTHS_FR,
)


def test_valid_date():
    # Months are now stored as numbers (1-12), language-agnostic.
    assert month_year_from_iso("2024-03-15") == (3, 2024)


def test_january_and_december_boundaries():
    assert month_year_from_iso("2025-01-01") == (1, 2025)
    assert month_year_from_iso("2025-12-31") == (12, 2025)


def test_none_or_empty_returns_none():
    assert month_year_from_iso(None) == (None, None)
    assert month_year_from_iso("") == (None, None)


def test_invalid_date_returns_none():
    assert month_year_from_iso("not-a-date") == (None, None)
    assert month_year_from_iso("2024-13-40") == (None, None)


def test_month_name_to_number_handles_accents_and_unaccented_variants():
    """Legacy data/export could hold both accented and unaccented French
    month names; both must resolve to the same 1-12 number."""
    assert month_name_to_number("Janvier") == 1
    assert month_name_to_number("Février") == 2
    assert month_name_to_number("Fevrier") == 2  # unaccented variant
    assert month_name_to_number("Août") == 8
    assert month_name_to_number("Aout") == 8  # unaccented variant
    assert month_name_to_number("décembre") == 12
    assert month_name_to_number("3") == 3  # digit string passthrough
    assert month_name_to_number("not-a-month") is None
    assert month_name_to_number(None) is None


def test_month_number_to_name_roundtrips_for_spreadsheet_format():
    """The exporter writes the spreadsheet's French 'MOIS FINI' column, so a
    number must map back to its French name."""
    assert month_number_to_name(1) == MONTHS_FR[0]
    assert month_number_to_name(2) == MONTHS_FR[1]
    assert month_number_to_name(12) == MONTHS_FR[11]
    assert month_number_to_name(None) is None
    assert month_number_to_name(0) is None
    assert month_number_to_name(13) is None
