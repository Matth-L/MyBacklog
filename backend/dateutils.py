"""Date utilities: derives a month/year (in the format used by the original
spreadsheet, in French) from an exact YYYY-MM-DD date."""
from datetime import date

MONTH_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
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
    return MONTH_FR[m - 1], y
