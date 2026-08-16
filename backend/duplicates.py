"""A game shouldn't normally exist in both Backlog and Completed at once —
usually it means the player finished something they forgot to remove from
the backlog. Detection here is always computed live from the current
database state (never cached/persisted), so it can't go stale: fix it by
actually resolving the duplicate (delete one copy, or rename one so they no
longer match) and it disappears on its own from every check below.

Nothing in this module ever deletes data — every function only *reports* a
conflict; the caller (an API route) decides what to do with it, and the
frontend always leaves the actual deletion to an explicit user action.
"""
from .db import get_conn
from .importer import _norm


def find_duplicates():
    """Every backlog/completed pair currently sharing a normalized title."""
    conn = get_conn()
    rows = conn.execute("SELECT id, title, status FROM games").fetchall()
    conn.close()

    backlog_by_norm, completed_by_norm = {}, {}
    for r in rows:
        bucket = backlog_by_norm if r["status"] == "backlog" else completed_by_norm
        bucket.setdefault(_norm(r["title"]), []).append({"id": r["id"], "title": r["title"]})

    pairs = []
    for norm_title, backlog_games in backlog_by_norm.items():
        completed_games = completed_by_norm.get(norm_title)
        if not completed_games:
            continue
        for b in backlog_games:
            for c in completed_games:
                pairs.append({
                    "backlog_id": b["id"], "backlog_title": b["title"],
                    "completed_id": c["id"], "completed_title": c["title"],
                })
    return pairs


def find_conflicting_game(title: str, status: str, exclude_id: int = None):
    """For create/status-change time checks: is there already a game with
    the same normalized title in the *other* status? `status` is the status
    the game is being saved as (so we look for a match in the opposite
    bucket). Returns that game's {id, title, status} dict, or None."""
    other_status = "completed" if status == "backlog" else "backlog"
    key = _norm(title)
    conn = get_conn()
    rows = conn.execute("SELECT id, title FROM games WHERE status = ?", (other_status,)).fetchall()
    conn.close()
    for r in rows:
        if exclude_id is not None and r["id"] == exclude_id:
            continue
        if _norm(r["title"]) == key:
            return {"id": r["id"], "title": r["title"], "status": other_status}
    return None
