"""Database layer (SQLite) for the MyBacklog application."""
import sqlite3
import os
import json
from pathlib import Path

DATA_DIR = Path(os.environ.get("BACKLOG_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "backlog.db"
CONFIG_PATH = DATA_DIR / "config.json"
COVERS_DIR = DATA_DIR / "covers"
COVERS_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'backlog',   -- 'backlog' or 'completed'
    cover_path TEXT,
    dlc INTEGER DEFAULT 0,
    abandoned INTEGER DEFAULT 0,               -- true if the game was abandoned (not actually finished)
    available INTEGER,                        -- do I currently own it? (1/0/NULL)
    hours_estimated REAL,
    hours_played REAL,
    duration_label TEXT,                      -- e.g. "2d", "1 year"
    date_completed TEXT,                      -- exact date (YYYY-MM-DD), if known
    month_finished TEXT,                      -- derived from date_completed, or imported as-is
    year_finished INTEGER,                    -- derived from date_completed, or imported as-is
    worth_it TEXT,                             -- Yes / No / Meh / PEAK
    rating REAL,                                -- rating out of 10 (decimals allowed, e.g. 7.5)
    review TEXT,
    notes TEXT,                                -- free-form comments
    priority INTEGER DEFAULT 0,                -- backlog ordering (play queue)
    date_added TEXT DEFAULT (datetime('now')),
    date_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orphan_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_title TEXT NOT NULL,
    review TEXT,
    linked_game_id INTEGER,
    suggested_game_id INTEGER,   -- best candidate found by approximate matching, awaiting user confirmation
    match_type TEXT,             -- 'fuzzy' (one clear candidate) | 'ambiguous' (several plausible) | NULL (no candidate at all)
    alternative_game_ids TEXT    -- JSON array of other plausible game ids, only set when match_type='ambiguous'
);

CREATE TABLE IF NOT EXISTS name_sanitization (
    game_id INTEGER PRIMARY KEY,      -- one row per game; ON CONFLICT(game_id) upserts
    name_hash TEXT NOT NULL,          -- hash of the title as of this check; a changed title = reprocess
    status TEXT NOT NULL,             -- 'pending' | 'sanitized' | 'rejected'
    suggested_name TEXT,              -- NULL unless status='pending'
    source TEXT,                      -- 'alias' | 'normalized' | 'fuzzy' | 'external' | NULL
    checked_at TEXT,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- 'status' and 'year_finished' are filtered on nearly every /api/games and
-- /api/stats query — cheap to keep indexed even at this app's modest scale,
-- and it matters once a library grows into the thousands of games.
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_year_finished ON games(year_finished);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    """Adds missing columns to databases created by an earlier version."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
    if "date_completed" not in cols:
        conn.execute("ALTER TABLE games ADD COLUMN date_completed TEXT")
    if "abandoned" not in cols:
        conn.execute("ALTER TABLE games ADD COLUMN abandoned INTEGER DEFAULT 0")

    orphan_cols = {row["name"] for row in conn.execute("PRAGMA table_info(orphan_reviews)").fetchall()}
    if "suggested_game_id" not in orphan_cols:
        conn.execute("ALTER TABLE orphan_reviews ADD COLUMN suggested_game_id INTEGER")
    if "match_type" not in orphan_cols:
        conn.execute("ALTER TABLE orphan_reviews ADD COLUMN match_type TEXT")
    if "alternative_game_ids" not in orphan_cols:
        conn.execute("ALTER TABLE orphan_reviews ADD COLUMN alternative_game_ids TEXT")


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"configured": False}


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def is_empty_db():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM games").fetchone()["c"]
    conn.close()
    return n == 0
