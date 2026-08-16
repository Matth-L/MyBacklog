"""Fuzzy text similarity alone can't tell "Dark Souls II" and "Dark Souls
III" apart — they're one character different and score very high on plain
ratio. This module extracts a sequel/entry number from a title (roman
numeral or arabic digit) so callers can penalize or reject candidates whose
numbers actively disagree, instead of trusting raw similarity — used by
cover art ranking, name sanitization, and review matching alike.
"""
import re

_ROMAN_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8,
    "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
}
_DIGIT_RE = re.compile(r"^\d{1,3}$")


def extract_sequel_number(normalized_title: str):
    """`normalized_title` should already be lowercased with punctuation
    collapsed to spaces (i.e. run through the caller's own _norm first).
    Returns the first roman-numeral or arabic-digit token found reading
    left to right (where sequel numbers conventionally sit, right after the
    base title and before any subtitle), or None if there isn't one."""
    if not normalized_title:
        return None
    for tok in normalized_title.split():
        if _DIGIT_RE.match(tok):
            n = int(tok)
            if 1 <= n <= 999:
                return n
        elif tok in _ROMAN_MAP:
            return _ROMAN_MAP[tok]
    return None


def sequel_conflict(norm_a: str, norm_b: str) -> bool:
    """True only when BOTH titles have an extractable sequel number AND
    those numbers disagree — a title with no number at all never conflicts
    with anything (not enough signal either way)."""
    na, nb = extract_sequel_number(norm_a), extract_sequel_number(norm_b)
    return na is not None and nb is not None and na != nb
