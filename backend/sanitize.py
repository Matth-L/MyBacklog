"""Suggests canonical game names (proper capitalization, full subtitles,
resolved abbreviations) to improve HowLongToBeat/cover-art/metadata matching
— without ever renaming anything automatically. Every suggestion is stored
and surfaced for the user to explicitly Accept or Reject.

Matching order (stops at the first hit):
  1. Exact local match   — title already equals a known canonical name.
  2. Alias match         — title is a known abbreviation/variant.
  3. Normalized match    — title matches a canonical name once
                            case/spacing/accents are ignored.
  4. Fuzzy match         — title is close enough to a known canonical name.
  5. External API        — Steam/RAWG/Giant Bomb (only if allowed by the
                            same internet-search consent used for cover
                            art), and only when nothing local worked. A
                            confident external hit is folded into the local
                            "learned" cache so it's available offline next
                            time — the app gets faster and more
                            offline-capable the more it's used.

Every game is only re-processed if its title actually changed since the
last check (a hash of the title is stored) — a full library scan on an
unchanged backlog does no work at all beyond a hash comparison.
"""
import re
import json
import time
import hashlib
import difflib
import unicodedata
import threading
from pathlib import Path

from .db import get_conn, load_config, DATA_DIR
from . import covers as cover_search
from . import sequel_guard

SEED_ALIASES_PATH = Path(__file__).resolve().parent / "data" / "aliases_seed.json"
LEARNED_ALIASES_PATH = DATA_DIR / "aliases_learned.json"

FUZZY_MIN_RATIO = 0.82  # deliberately stricter than review-matching: a wrong
                         # rename is more disruptive than an unmatched review


def _norm(s):
    if not s:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _name_hash(title: str) -> str:
    return hashlib.sha1(_norm(title).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_aliases() -> dict:
    """Seed (bundled with the app) + learned (grows locally over time),
    both keyed by normalized alias -> canonical display name. Learned
    entries win on conflict since they reflect this user's own data."""
    aliases = _load_json(SEED_ALIASES_PATH)
    aliases.update(_load_json(LEARNED_ALIASES_PATH))
    return aliases


def _remember_alias(alias_norm: str, canonical: str):
    learned = _load_json(LEARNED_ALIASES_PATH)
    learned[alias_norm] = canonical
    LEARNED_ALIASES_PATH.write_text(json.dumps(learned, ensure_ascii=False, indent=2), encoding="utf-8")


def find_canonical_suggestion(title: str, allow_external: bool = True):
    """Runs the matching pipeline for one title. Returns
    (suggested_name, source) or (None, None) if the title already looks
    canonical / nothing better was found. Never touches the database —
    purely a lookup."""
    if not title or not title.strip():
        return None, None
    key = _norm(title)
    aliases = load_aliases()
    canonical_values_norm = {_norm(v): v for v in aliases.values()}

    # 1. Exact local match: already a recognized canonical name.
    if key in canonical_values_norm and canonical_values_norm[key] == title:
        return None, None

    # 2. Alias match: a known abbreviation/variant.
    if key in aliases and aliases[key] != title:
        return aliases[key], "alias"

    # 3. Normalized match: same as a canonical name modulo formatting.
    if key in canonical_values_norm and canonical_values_norm[key] != title:
        return canonical_values_norm[key], "normalized"

    # 4. Fuzzy match against every known canonical name.
    best_name, best_ratio = None, 0.0
    for norm_v, display_v in canonical_values_norm.items():
        if sequel_guard.sequel_conflict(key, norm_v):
            continue  # e.g. never suggest "Dark Souls III" for "Dark Souls II"
        ratio = difflib.SequenceMatcher(None, key, norm_v).ratio()
        if ratio > best_ratio:
            best_name, best_ratio = display_v, ratio
    if best_ratio >= FUZZY_MIN_RATIO and best_name != title:
        return best_name, "fuzzy"

    # 5. External API — last resort, and only with consent (same gate as
    # cover art search) since it's a network call.
    if not allow_external:
        return None, None
    cfg = load_config()
    if not cfg.get("internet_search_consent"):
        return None, None

    rawg_key = cfg.get("rawg_api_key") or None
    giantbomb_key = cfg.get("giantbomb_api_key") or None
    candidates = []
    for variant in cover_search._query_variants(title):
        candidates += cover_search._search_steam(variant)
        if rawg_key:
            candidates += cover_search._search_rawg(variant, rawg_key)
        if giantbomb_key:
            candidates += cover_search._search_giantbomb(variant, giantbomb_key)
        if candidates:
            break
    best_ext, best_ext_ratio = None, 0.0
    for c in candidates:
        name = c.get("name")
        if not name:
            continue
        norm_name = _norm(name)
        if sequel_guard.sequel_conflict(key, norm_name):
            continue  # e.g. never suggest "Dark Souls III" for "Dark Souls II"
        ratio = difflib.SequenceMatcher(None, key, norm_name).ratio()
        if ratio > best_ext_ratio:
            best_ext, best_ext_ratio = name, ratio
    if best_ext and best_ext_ratio >= FUZZY_MIN_RATIO and best_ext != title:
        _remember_alias(key, best_ext)  # cached locally: offline next time
        return best_ext, "external"

    return None, None


# --------------------------------------------------------------------------
# Persistence: one row per game, hash-gated so unchanged titles are never
# reprocessed. Mirrors backend.covers' bulk-fill threading pattern so a full
# library scan never blocks the UI.
# --------------------------------------------------------------------------

def get_status(game_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM name_sanitization WHERE game_id = ?", (game_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_pending():
    conn = get_conn()
    rows = conn.execute(
        """SELECT n.*, g.title AS current_title FROM name_sanitization n
           JOIN games g ON g.id = n.game_id
           WHERE n.status = 'pending'"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def accept_suggestion(game_id: int) -> bool:
    """Applies the suggested name to the game (same row, same id — a rename,
    never a new game) and marks this sanitization as resolved."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM name_sanitization WHERE game_id = ?", (game_id,)).fetchone()
    if not row or not row["suggested_name"]:
        conn.close()
        return False
    new_title = row["suggested_name"]
    conn.execute("UPDATE games SET title = ?, date_updated = datetime('now') WHERE id = ?",
                 (new_title, game_id))
    conn.execute(
        "UPDATE name_sanitization SET status = 'sanitized', name_hash = ?, checked_at = datetime('now') "
        "WHERE game_id = ?",
        (_name_hash(new_title), game_id),
    )
    conn.commit()
    conn.close()
    return True


def reject_suggestion(game_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute(
        """INSERT INTO name_sanitization (game_id, name_hash, status, suggested_name, source, checked_at)
           VALUES (?, ?, 'rejected', NULL, NULL, datetime('now'))
           ON CONFLICT(game_id) DO UPDATE SET
             status='rejected', suggested_name=NULL, source=NULL,
             name_hash=excluded.name_hash, checked_at=datetime('now')""",
        (game_id, _name_hash(row["title"])),
    )
    conn.commit()
    conn.close()
    return True


_scan_state = {"running": False, "total": 0, "done": 0, "suggested": 0, "current": None, "cancel": False}
_scan_lock = threading.Lock()
SCAN_DELAY_SECONDS = 0.05  # only relevant when external lookups happen; local-only checks are instant


def get_scan_status():
    with _scan_lock:
        return dict(_scan_state)


def cancel_scan():
    with _scan_lock:
        _scan_state["cancel"] = True


def _scan_worker(allow_external: bool):
    conn = get_conn()
    games = conn.execute("SELECT id, title FROM games").fetchall()
    cached = {r["game_id"]: r for r in conn.execute("SELECT * FROM name_sanitization").fetchall()}
    conn.close()

    with _scan_lock:
        _scan_state.update({"total": len(games), "done": 0, "suggested": 0, "current": None})

    for g in games:
        with _scan_lock:
            if _scan_state["cancel"]:
                break
            _scan_state["current"] = g["title"]

        current_hash = _name_hash(g["title"])
        prior = cached.get(g["id"])
        # Hash unchanged since a decision was already made: skip entirely,
        # no local computation and no network call.
        if prior and prior["name_hash"] == current_hash and prior["status"] in ("sanitized", "rejected", "pending"):
            with _scan_lock:
                _scan_state["done"] += 1
            continue

        try:
            suggestion, source = find_canonical_suggestion(g["title"], allow_external=allow_external)
        except Exception:
            suggestion, source = None, None

        conn = get_conn()
        if suggestion:
            conn.execute(
                """INSERT INTO name_sanitization (game_id, name_hash, status, suggested_name, source, checked_at)
                   VALUES (?, ?, 'pending', ?, ?, datetime('now'))
                   ON CONFLICT(game_id) DO UPDATE SET
                     status='pending', suggested_name=excluded.suggested_name,
                     source=excluded.source, name_hash=excluded.name_hash, checked_at=datetime('now')""",
                (g["id"], current_hash, suggestion, source),
            )
            with _scan_lock:
                _scan_state["suggested"] += 1
        else:
            # Nothing to suggest — still record the hash so an unchanged
            # title is never reprocessed, without claiming a fake "pending".
            conn.execute(
                """INSERT INTO name_sanitization (game_id, name_hash, status, suggested_name, source, checked_at)
                   VALUES (?, ?, 'sanitized', NULL, NULL, datetime('now'))
                   ON CONFLICT(game_id) DO UPDATE SET
                     status='sanitized', suggested_name=NULL, source=NULL,
                     name_hash=excluded.name_hash, checked_at=datetime('now')""",
                (g["id"], current_hash),
            )
        conn.commit()
        conn.close()

        with _scan_lock:
            _scan_state["done"] += 1
        if source == "external":
            time.sleep(SCAN_DELAY_SECONDS)

    with _scan_lock:
        _scan_state["running"] = False
        _scan_state["current"] = None


def start_scan(allow_external: bool = True) -> bool:
    with _scan_lock:
        if _scan_state["running"]:
            return False
        _scan_state.update({"running": True, "cancel": False, "total": 0, "done": 0,
                             "suggested": 0, "current": None})
    t = threading.Thread(target=_scan_worker, args=(allow_external,), daemon=True)
    t.start()
    return True
