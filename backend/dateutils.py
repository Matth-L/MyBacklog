"""Date utilities: derives a month/year (in the format used by the original
spreadsheet, in French) from an exact YYYY-MM-DD date.

MONTHS_FR is the single, canonical French month-name list used wherever a
month name is needed (derivation, stats, export). One source avoids the drift
that previously saw stats.py look for the unaccented forms while dateutils
emitted the accented ones, silently dropping February/August games from the
monthly chart.
"""
from datetime import date

MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def month_year_from_iso(date_str):
    """('2024-03-15') -> ('Mars', 2024). Returns (None, None) if invalid."""
    if not date_str:
        return None, None
    try:
        y, m, d = (int(p) for p in str(date_str).strip().split("-")[:3])
        date(y, m, d)  # validate that it's a real date
    except (ValueError, TypeError):
        return None, None
    return MONTHS_FR[m - 1], y
