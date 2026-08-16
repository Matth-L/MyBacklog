"""HowLongToBeat integration.

Unlike the cover-art sources, this is never queried automatically: the
frontend only calls fetch_estimated_hours() when the user explicitly clicks
"Fetch HowLongToBeat" on a game that has no playtime estimate yet."""
from howlongtobeatpy import HowLongToBeat

MODE_FIELDS = {
    "main": "main_story",
    "main_extra": "main_extra",
    "completionist": "completionist",
}


class HLTBError(Exception):
    pass


def fetch_estimated_hours(title: str, mode: str = "main"):
    """Searches HowLongToBeat for `title` and returns the estimated hours for
    the requested `mode` (main / main_extra / completionist) from the best
    matching result, or None if nothing usable was found."""
    if mode not in MODE_FIELDS:
        raise HLTBError(f"Unknown mode: {mode}")
    if not title or not title.strip():
        return None

    try:
        results = HowLongToBeat().search(title.strip())
    except Exception:
        # Network hiccup, HLTB layout change, etc. — never let this take
        # down the request; the caller treats None as "nothing found".
        return None

    if not results:
        return None

    best = max(results, key=lambda e: e.similarity)
    hours = getattr(best, MODE_FIELDS[mode], None)
    if not hours or hours <= 0:
        return None
    return round(float(hours), 1)
