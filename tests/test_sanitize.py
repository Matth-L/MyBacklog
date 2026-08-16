import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def temp_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKLOG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BACKLOG_BACKUP_DIR", str(tmp_path / "backup_backlog"))
    monkeypatch.setenv("BACKLOG_COVER_ART_DIR", str(tmp_path / "cover_art"))
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]
    from backend import db as db_module
    db_module.init_db()
    yield tmp_path


# ------------------------------------------------------------- Matching pipeline order

def test_alias_match_is_found_before_fuzzy_or_external(temp_env):
    from backend import sanitize

    name, source = sanitize.find_canonical_suggestion("Ni no Kuni", allow_external=False)
    assert source == "alias"
    assert name == "Ni no Kuni: Wrath of the White Witch"


def test_exact_canonical_match_returns_no_suggestion(temp_env):
    from backend import sanitize

    name, source = sanitize.find_canonical_suggestion(
        "The Legend of Zelda: Breath of the Wild", allow_external=False
    )
    assert name is None and source is None


def test_normalized_match_ignores_case_and_spacing(temp_env):
    from backend import sanitize

    name, source = sanitize.find_canonical_suggestion(
        "the legend of zelda:   breath of the wild", allow_external=False
    )
    assert source == "normalized"
    assert name == "The Legend of Zelda: Breath of the Wild"


def test_fuzzy_match_catches_close_misspelling(temp_env):
    from backend import sanitize

    name, source = sanitize.find_canonical_suggestion("Grand Theft Auto 5", allow_external=False)
    # "Grand Theft Auto 5" isn't the exact alias "gta5"/"gta 5" text, but is
    # close enough to the canonical "Grand Theft Auto V" to fuzzy-match.
    assert source in ("fuzzy", "alias")
    assert name == "Grand Theft Auto V"


def test_unrecognizable_title_with_external_disabled_returns_nothing(temp_env):
    from backend import sanitize

    name, source = sanitize.find_canonical_suggestion("Some Totally Unknown Indie Game Xyz123", allow_external=False)
    assert name is None and source is None


def test_never_suggests_external_without_consent(temp_env, monkeypatch):
    from backend import sanitize
    from backend.db import save_config

    save_config({"configured": True, "internet_search_consent": False})
    called = {"n": 0}
    monkeypatch.setattr(sanitize.cover_search, "_search_steam", lambda q: (called.__setitem__("n", called["n"] + 1), [])[1])

    name, source = sanitize.find_canonical_suggestion("Some Totally Unknown Game", allow_external=True)
    assert name is None and source is None
    assert called["n"] == 0  # never even queried without consent


def test_external_match_is_learned_locally(temp_env, monkeypatch):
    from backend import sanitize
    from backend.db import save_config

    save_config({"configured": True, "internet_search_consent": True})
    monkeypatch.setattr(sanitize.cover_search, "_search_steam",
                         lambda q: [{"name": "Some Totally Unknown Game: Definitive Edition"}])
    monkeypatch.setattr(sanitize.cover_search, "_search_rawg", lambda q, k: [])
    monkeypatch.setattr(sanitize.cover_search, "_search_giantbomb", lambda q, k: [])
    monkeypatch.setattr(sanitize, "FUZZY_MIN_RATIO", 0.5)  # loosen for this synthetic example

    name, source = sanitize.find_canonical_suggestion("Some Totally Unknown Game", allow_external=True)
    assert source == "external"
    assert name == "Some Totally Unknown Game: Definitive Edition"

    # Now available offline (no external calls needed this time).
    monkeypatch.setattr(sanitize.cover_search, "_search_steam", lambda q: (_ for _ in ()).throw(AssertionError("should not be called")))
    name2, source2 = sanitize.find_canonical_suggestion("Some Totally Unknown Game", allow_external=True)
    assert source2 == "alias"
    assert name2 == "Some Totally Unknown Game: Definitive Edition"


# ------------------------------------------------------------- Accept / reject / never auto-rename

def test_scan_never_auto_renames_only_suggests(temp_env):
    from backend import sanitize
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Ni no Kuni', 'backlog')")
    conn.commit()
    game_id = conn.execute("SELECT id FROM games").fetchone()["id"]
    conn.close()

    sanitize.start_scan(allow_external=False)
    import time
    for _ in range(50):
        if not sanitize.get_scan_status()["running"]:
            break
        time.sleep(0.05)

    conn = get_conn()
    game = conn.execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    assert game["title"] == "Ni no Kuni"  # untouched

    pending = sanitize.list_pending()
    assert len(pending) == 1
    assert pending[0]["suggested_name"] == "Ni no Kuni: Wrath of the White Witch"
    assert pending[0]["current_title"] == "Ni no Kuni"


def test_accept_suggestion_renames_same_row_same_id(temp_env):
    from backend import sanitize
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status, cover_path) VALUES ('Ni no Kuni', 'backlog', '/x.jpg')")
    conn.commit()
    game_id = conn.execute("SELECT id FROM games").fetchone()["id"]
    conn.close()

    suggestion, source = sanitize.find_canonical_suggestion("Ni no Kuni", allow_external=False)
    conn = get_conn()
    conn.execute(
        "INSERT INTO name_sanitization (game_id, name_hash, status, suggested_name, source, checked_at) "
        "VALUES (?, 'x', 'pending', ?, ?, datetime('now'))",
        (game_id, suggestion, source),
    )
    conn.commit()
    conn.close()

    ok = sanitize.accept_suggestion(game_id)
    assert ok is True

    conn = get_conn()
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    assert game["id"] == game_id  # same stable id
    assert game["title"] == "Ni no Kuni: Wrath of the White Witch"
    assert game["cover_path"] == "/x.jpg"  # unrelated data untouched


def test_reject_suggestion_keeps_original_title(temp_env):
    from backend import sanitize
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Ni no Kuni', 'backlog')")
    conn.commit()
    game_id = conn.execute("SELECT id FROM games").fetchone()["id"]
    conn.close()

    ok = sanitize.reject_suggestion(game_id)
    assert ok is True

    conn = get_conn()
    game = conn.execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()
    status_row = conn.execute("SELECT status FROM name_sanitization WHERE game_id = ?", (game_id,)).fetchone()
    conn.close()
    assert game["title"] == "Ni no Kuni"
    assert status_row["status"] == "rejected"


# ------------------------------------------------------------- Hash-based caching (skip unchanged)

def test_unchanged_title_is_not_reprocessed(temp_env, monkeypatch):
    from backend import sanitize
    from backend.db import get_conn
    import time

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Celeste', 'backlog')")
    conn.commit()
    conn.close()

    call_count = {"n": 0}
    real_find = sanitize.find_canonical_suggestion

    def counting_find(*a, **k):
        call_count["n"] += 1
        return real_find(*a, **k)
    monkeypatch.setattr(sanitize, "find_canonical_suggestion", counting_find)

    sanitize.start_scan(allow_external=False)
    for _ in range(50):
        if not sanitize.get_scan_status()["running"]:
            break
        time.sleep(0.05)
    first_calls = call_count["n"]
    assert first_calls == 1

    # Re-run the scan with nothing changed — should skip entirely.
    sanitize.start_scan(allow_external=False)
    for _ in range(50):
        if not sanitize.get_scan_status()["running"]:
            break
        time.sleep(0.05)
    assert call_count["n"] == first_calls  # no new calls


def test_renamed_title_is_reprocessed(temp_env):
    from backend import sanitize
    from backend.db import get_conn
    import time

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Celeste', 'backlog')")
    conn.commit()
    game_id = conn.execute("SELECT id FROM games").fetchone()["id"]
    conn.close()

    sanitize.start_scan(allow_external=False)
    for _ in range(50):
        if not sanitize.get_scan_status()["running"]:
            break
        time.sleep(0.05)

    status1 = sanitize.get_status(game_id)
    assert status1["status"] == "sanitized"

    conn = get_conn()
    conn.execute("UPDATE games SET title = 'Ni no Kuni' WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()

    sanitize.start_scan(allow_external=False)
    for _ in range(50):
        if not sanitize.get_scan_status()["running"]:
            break
        time.sleep(0.05)

    status2 = sanitize.get_status(game_id)
    assert status2["status"] == "pending"
    assert status2["suggested_name"] == "Ni no Kuni: Wrath of the White Witch"
