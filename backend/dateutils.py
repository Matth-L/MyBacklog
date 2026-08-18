"""Date utilities: derives a month (1-12) and year from an exact YYYY-MM-DD
date, and converts between month numbers and the French month names used by
the original spreadsheet format.

Months are stored in the database as plain integers (1-12), so the data is
language-agnostic; the frontend translates a number to the user's locale for
display. The French name <-> number helpers here exist only for the import
(the spreadsheet's "MOIS FINI" column is a French name) and the export (which
writes that column back as a French name to preserve the original format).
"""
from datetime import date
import re
import unicodedata

MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

# Normalized (accent/case/space-insensitive) French name -> month number,
# built once. Tolerates the unaccented forms ("Fevrier", "Aout") that older
# data/exports contained, so legacy months are migrated/imported correctly.
_MONTH_NAME_INDEX = {}


def _build_month_index():
    if _MONTH_NAME_INDEX:
        return
    for i, name in enumerate(MONTHS_FR, start=1):
        _MONTH_NAME_INDEX[_norm(name)] = i
    # Also accept the unaccented variants explicitly (already covered by
    # _norm stripping accents, but be defensive against any future drift).
    _MONTH_NAME_INDEX["fevrier"] = 2
    _MONTH_NAME_INDEX["aout"] = 8


def _norm(s):
    if not s:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s).strip()


def month_year_from_iso(date_str):
    """('2024-03-15') -> (3, 2024). Returns (None, None) if invalid. The month
    is an integer 1-12 (language-agnostic); the frontend translates it."""
    if not date_str:
        return None, None
    try:
        y, m, d = (int(p) for p in str(date_str).strip().split("-")[:3])
        date(y, m, d)  # validate that it's a real date
    except (ValueError, TypeError):
        return None, None
    return m, y


def month_name_to_number(name):
    """Converts a French month name (or any unaccented variant, or a digit)
    to its 1-12 number. Returns None when unrecognized. Used to migrate
    legacy string months and to parse imported spreadsheet data."""
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None
    _build_month_index()
    return _MONTH_NAME_INDEX.get(_norm(s))


def month_number_to_name(n):
    """Converts a 1-12 number to its French month name (the spreadsheet
    format). Returns None for out-of-range/None. Used only by the exporter."""
    if n is None:
        return None
    try:
        n = int(n)
    except (ValueError, TypeError):
        return None
    return MONTHS_FR[n - 1] if 1 <= n <= 12 else None
