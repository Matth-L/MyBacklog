import os
import time
import json
import gzip
import logging
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from werkzeug.utils import secure_filename

from backend.db import init_db, get_conn, load_config, save_config, is_empty_db, DATA_DIR, COVERS_DIR
from backend.importer import import_all
from backend import exporter
from backend.stats import compute_stats, list_review_years, build_year_review
from backend import covers as cover_search
from backend import backup as backup_mgr
from backend import session as session_mgr
from backend import hltb
from backend import duplicates as dup_mgr
from backend import sanitize as sanitize_mgr
from backend import applog
from backend.dateutils import month_year_from_iso, month_name_to_number

# Silence Werkzeug's per-request access log (every GET/POST line) — only the
# clean, curated events logged via backend.applog are printed. Errors still
# surface through Flask's own error handling below.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Caps the raw size of any incoming request body (file uploads, Excel
# imports, etc.). Generous for even a huge personal backlog spreadsheet or
# a batch of cover images, but bounds worst-case memory use against an
# oversized or maliciously crafted upload rather than accepting an
# unlimited body size (Flask has no default limit).
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
UPLOAD_TMP = DATA_DIR / "uploads_tmp"
UPLOAD_TMP.mkdir(parents=True, exist_ok=True)

# This is a single-user app with no login/auth of any kind, so whether it's
# reachable from other devices matters a lot. Defaults to localhost-only;
# set BACKLOG_ALLOW_LAN=1 to explicitly opt into listening on every network
# interface (e.g. to reach it from a phone on the same Wi-Fi, or because
# it's running inside a container where the container's own loopback isn't
# reachable from the host). See __main__ below for where this drives the
# actual bind address, and session_import() below for the one route it also
# gates off entirely once LAN access is allowed.
app.config["BACKLOG_ALLOW_LAN"] = os.environ.get("BACKLOG_ALLOW_LAN") == "1"

init_db()

# ----------------------------------------------------------------- Response compression
# Every /api/games response ships the full row for every game (including
# free-form review/notes text), and app.js alone is ~190KB — both are highly
# repetitive text that gzip shrinks dramatically (typically 70-90%). Rather
# than pull in an extra dependency (Flask-Compress) for what's a fairly
# small transform, this compresses in place for any client that says it
# accepts gzip.
_COMPRESSIBLE_MIMETYPES = {
    "application/json", "text/html", "text/css", "text/javascript",
    "application/javascript", "image/svg+xml", "text/plain", "text/xml",
}
_COMPRESS_MIN_BYTES = 500  # below this, gzip's own overhead isn't worth it


@app.after_request
def compress_response(response):
    if response.direct_passthrough:
        # Set by send_file/send_from_directory for on-disk files (cover
        # images, xlsx/zip exports...) — already binary/pre-compressed
        # formats, and re-reading the body here would defeat the point of
        # passthrough streaming in the first place.
        return response
    if response.mimetype not in _COMPRESSIBLE_MIMETYPES:
        return response
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return response
    if response.headers.get("Content-Encoding"):
        return response  # already encoded upstream; don't double-compress
    data = response.get_data()
    if len(data) < _COMPRESS_MIN_BYTES:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    # Tells any cache (browser, proxy) that the response body differs by
    # this header, so a gzip-encoded response is never served to a client
    # that didn't ask for it.
    vary = response.headers.get("Vary")
    response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
    return response


# ----------------------------------------------------------------- Frontend
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico")


# ----------------------------------------------------------------- Setup
@app.route("/api/setup/status")
def setup_status():
    cfg = load_config()
    cfg["has_data"] = not is_empty_db()
    return jsonify(cfg)


@app.route("/api/setup/import", methods=["POST"])
def setup_import():
    """Accepts either a .xlsx file (key 'xlsx'), or 3 csv files
    (keys 'backlog_csv', 'avis_csv', 'complete_csv')."""
    saved = {}
    for key in ("xlsx", "backlog_csv", "avis_csv", "complete_csv"):
        f = request.files.get(key)
        if f and f.filename:
            path = UPLOAD_TMP / secure_filename(f.filename)
            f.save(path)
            saved[key] = str(path)

    if not saved:
        return jsonify({"error": "no_file_received"}), 400

    try:
        summary = import_all(
            xlsx_path=saved.get("xlsx"),
            backlog_csv=saved.get("backlog_csv"),
            avis_csv=saved.get("avis_csv"),
            complete_csv=saved.get("complete_csv"),
        )
    except Exception as e:
        return jsonify({"error": "import_failed", "detail": str(e)}), 400

    cfg = load_config()
    cfg["configured"] = True
    cfg["source"] = list(saved.keys())
    save_config(cfg)
    backup_mgr.create_backup(reason="post-import")

    duplicates = dup_mgr.find_duplicates()
    if duplicates:
        summary["duplicates_found"] = len(duplicates)
        applog.info(f"Import found {len(duplicates)} backlog/completed title duplicate(s).")

    return jsonify({"ok": True, "summary": summary})


@app.route("/api/setup/skip", methods=["POST"])
def setup_skip():
    """Start with an empty backlog, without importing."""
    cfg = load_config()
    cfg["configured"] = True
    cfg["source"] = "empty"
    save_config(cfg)
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Session (import at any time)
def _do_session_import(path: str):
    """Shared by both the path-based and file-upload session-import routes."""
    try:
        summary = session_mgr.import_new_session(path)
    except session_mgr.SessionImportError as e:
        # Propagate the specific machine-readable code + detail (matches an
        # err_<code> key in the frontend's translation tables) rather than
        # squashing every recoverable import failure into one generic
        # "import_failed" message.
        return jsonify({"error": e.code, "detail": e.detail}), 400
    except Exception as e:
        applog.error(f"Session import failed: {e}")
        return jsonify({"error": "import_failed", "detail": str(e)}), 400
    applog.info(f"Session import from: {path}")
    duplicates = dup_mgr.find_duplicates()
    if duplicates:
        summary["duplicates_found"] = len(duplicates)
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/session/import", methods=["POST"])
def session_import():
    """Import another Excel/session at any time (not just first setup).
    Always clears the current session first. Accepts a local path to a
    .xlsx file or a MyBacklog session .zip (as produced by /api/export/*).
    Kept for scripting/automation use; the Settings UI itself now uses the
    file-picker endpoint below instead of asking the user to type a path.

    Disabled whenever BACKLOG_ALLOW_LAN is set: this route lets the caller
    name *any* file path on the machine the server has read access to. On
    localhost-only that's just the same user asking the app to read their
    own files, but once the app is reachable from other devices on the
    network, that turns into an arbitrary-file-read primitive for anyone
    who can reach this port. The file-picker upload endpoint below covers
    the normal UI use case without this risk and stays enabled either way.
    """
    if app.config["BACKLOG_ALLOW_LAN"]:
        return jsonify({"error": "path_import_disabled_on_lan"}), 403
    data = request.get_json(force=True) or {}
    path = (data.get("path") or "").strip()
    if not path:
        return jsonify({"error": "file_path_required"}), 400
    return _do_session_import(path)


@app.route("/api/session/import-file", methods=["POST"])
def session_import_file():
    """Same as /api/session/import, but for the normal case: the user picks
    a file from a browser file input instead of typing a filesystem path."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no_file_received"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in (".xlsx", ".zip"):
        return jsonify({"error": "unsupported_session_format"}), 400
    dest = UPLOAD_TMP / secure_filename(f.filename)
    f.save(dest)
    try:
        return _do_session_import(str(dest))
    finally:
        dest.unlink(missing_ok=True)


# ----------------------------------------------------------------- Games CRUD
def _row_to_dict(row):
    d = dict(row)
    return d


@app.route("/api/games", methods=["GET"])
def list_games():
    status = request.args.get("status")  # 'backlog' | 'completed' | None
    q = request.args.get("q", "").strip()
    available = request.args.get("available")  # '1' | '0' | None
    year = request.args.get("year")  # exact year | None
    dlc = request.args.get("dlc")  # '1' (only DLC) | '0' (hide DLC) | None
    abandoned = request.args.get("abandoned")  # '1' (only abandoned) | '0' (hide abandoned) | None
    conn = get_conn()
    sql = "SELECT * FROM games WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        sql += " AND title LIKE ?"
        params.append(f"%{q}%")
    if available in ("0", "1"):
        sql += " AND available = ?"
        params.append(int(available))
    if year:
        sql += " AND year_finished = ?"
        params.append(int(year))
    if dlc in ("0", "1"):
        sql += " AND dlc = ?"
        params.append(int(dlc))
    if abandoned in ("0", "1"):
        sql += " AND abandoned = ?"
        params.append(int(abandoned))
    sql += " ORDER BY priority DESC, date_added DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([_row_to_dict(r) for r in rows])


@app.route("/api/games/years")
def list_years():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT year_finished FROM games WHERE status='completed' AND year_finished IS NOT NULL "
        "ORDER BY year_finished DESC"
    ).fetchall()
    conn.close()
    return jsonify([r["year_finished"] for r in rows])


@app.route("/api/games/<int:game_id>", methods=["GET"])
def get_game(game_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_row_to_dict(row))


FIELDS = ["title", "status", "cover_path", "dlc", "abandoned", "available", "hours_estimated",
          "hours_played", "duration_label", "date_completed", "month_finished", "year_finished",
          "worth_it", "rating", "review", "notes", "priority"]


def _apply_derived_date(data: dict):
    """If an exact completion date is provided, automatically derives the
    month (1-12) and year from it, rather than leaving a disconnected
    counter to fill in by hand. The month is stored as a number so the data
    stays language-agnostic; the frontend translates it for display."""
    # Normalize a legacy French month name (e.g. on a PUT carrying old data)
    # to a number once, here, so everything downstream deals with ints.
    if data.get("month_finished") and not str(data["month_finished"]).isdigit():
        data["month_finished"] = month_name_to_number(data["month_finished"])
    if data.get("date_completed"):
        month, year = month_year_from_iso(data["date_completed"])
        if month:
            data["month_finished"] = month
            data["year_finished"] = year


@app.route("/api/games", methods=["POST"])
def create_game():
    data = request.get_json(force=True)
    if not data.get("title"):
        return jsonify({"error": "title_required"}), 400
    data.setdefault("status", "backlog")

    if not data.get("force_duplicate"):
        conflict = dup_mgr.find_conflicting_game(data["title"], data["status"])
        if conflict:
            return jsonify({
                "error": "duplicate",
                "conflict": conflict,
            }), 409
    data.pop("force_duplicate", None)

    # A game created directly as "finished" is assumed owned by default
    # (you played it, by definition); the user can change that.
    if data["status"] == "completed" and "available" not in data:
        data["available"] = 1
    _apply_derived_date(data)
    cols = [f for f in FIELDS if f in data]
    placeholders = ", ".join("?" for _ in cols)
    conn = get_conn()
    cur = conn.execute(
        f"INSERT INTO games ({', '.join(cols)}) VALUES ({placeholders})",
        [data[c] for c in cols],
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM games WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    backup_mgr.create_backup(reason="new-game")
    return jsonify(_row_to_dict(row)), 201


@app.route("/api/games/<int:game_id>", methods=["PUT", "PATCH"])
def update_game(game_id):
    data = request.get_json(force=True)
    existing = conn_fetch_one("SELECT title, status FROM games WHERE id = ?", (game_id,))

    status_is_changing = (
        existing and data.get("status") and data["status"] != existing["status"]
    )
    if status_is_changing and not data.get("force_duplicate"):
        title_for_check = data.get("title") or existing["title"]
        conflict = dup_mgr.find_conflicting_game(title_for_check, data["status"], exclude_id=game_id)
        if conflict:
            return jsonify({"error": "duplicate", "conflict": conflict}), 409
    data.pop("force_duplicate", None)

    # Defaults to "owned" at the exact moment a game switches to "finished"
    # — only at that transition, never re-checked afterwards (a game that's
    # already finished keeps the value the user chose, even if they set it
    # back to "No" or "unset" afterwards).
    if data.get("status") == "completed" and "available" not in data:
        if existing and existing["status"] != "completed":
            data["available"] = 1
    _apply_derived_date(data)
    cols = [f for f in FIELDS if f in data]
    if not cols:
        return jsonify({"error": "nothing_to_update"}), 400
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    conn = get_conn()
    conn.execute(
        f"UPDATE games SET {set_clause}, date_updated = datetime('now') WHERE id = ?",
        [data[c] for c in cols] + [game_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not_found"}), 404
    # Backup only triggered by an explicit action: here, editing a review
    # (not on every small field change).
    if "review" in data:
        backup_mgr.create_backup(reason="review-edit")
    return jsonify(_row_to_dict(row))


@app.route("/api/hltb/lookup", methods=["POST"])
def lookup_hltb():
    """Same HowLongToBeat lookup as fetch_hltb below, but by a raw title
    instead of a saved game id, and it never touches the DB. Lets the "new
    game" modal offer the estimate while the game doesn't exist yet —
    the value is only persisted when the user hits Save, same as every
    other field in that form."""
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    mode = data.get("mode", "main")
    if mode not in hltb.MODE_FIELDS:
        return jsonify({"error": "invalid_mode"}), 400
    if not title:
        return jsonify({"error": "no_hltb_match", "code": "no_match"}), 404

    hours = hltb.fetch_estimated_hours(title, mode)
    if hours is None:
        return jsonify({"error": "no_hltb_match", "code": "no_match"}), 404

    applog.info(f"HowLongToBeat estimate looked up for '{title}': {hours}h ({mode}).")
    return jsonify({"hours_estimated": hours, "mode": mode})


@app.route("/api/games/<int:game_id>/fetch-hltb", methods=["POST"])
def fetch_hltb(game_id):
    """Fetches an estimated playtime from HowLongToBeat. Only ever called by
    an explicit user click (never automatically). The frontend only shows
    the "Fetch HowLongToBeat" control while the hours-estimated field is
    empty — including the moment the user clears it, before pressing Save —
    so gating "no playtime yet" is the UI's job, not a check against the
    last-saved DB value (which could be stale mid-edit)."""
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "main")
    if mode not in hltb.MODE_FIELDS:
        return jsonify({"error": "invalid_mode"}), 400

    game = conn_fetch_one("SELECT title FROM games WHERE id = ?", (game_id,))
    if not game:
        return jsonify({"error": "not_found"}), 404

    hours = hltb.fetch_estimated_hours(game["title"], mode)
    if hours is None:
        return jsonify({"error": "no_hltb_match", "code": "no_match"}), 404

    conn = get_conn()
    conn.execute(
        "UPDATE games SET hours_estimated = ?, date_updated = datetime('now') WHERE id = ?",
        (hours, game_id),
    )
    conn.commit()
    conn.close()
    applog.info(f"HowLongToBeat estimate fetched for '{game['title']}': {hours}h ({mode}).")
    return jsonify({"hours_estimated": hours, "mode": mode})


@app.route("/api/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    conn = get_conn()
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))

    # Deleting a game must never leave a stale reference in a *pending*
    # orphan-review suggestion — otherwise confirming it later would
    # silently do nothing (UPDATE against a game id that no longer
    # exists), while the review would still be marked as resolved.
    orphans = conn.execute(
        "SELECT id, suggested_game_id, alternative_game_ids FROM orphan_reviews WHERE linked_game_id IS NULL"
    ).fetchall()
    for o in orphans:
        alt_ids = json.loads(o["alternative_game_ids"]) if o["alternative_game_ids"] else []
        alt_ids = [a for a in alt_ids if a != game_id]
        if o["suggested_game_id"] == game_id:
            # The primary suggestion was deleted: promote the best
            # remaining alternative if there is one, otherwise fall back
            # to a plain unmatched orphan rather than a dangling id.
            new_suggested = alt_ids[0] if alt_ids else None
            new_alts = alt_ids[1:] if alt_ids else []
            new_type = "fuzzy" if new_suggested and not new_alts else ("ambiguous" if new_suggested else None)
            conn.execute(
                "UPDATE orphan_reviews SET suggested_game_id = ?, alternative_game_ids = ?, match_type = ? WHERE id = ?",
                (new_suggested, json.dumps(new_alts) if new_alts else None, new_type, o["id"]),
            )
        elif len(alt_ids) != len(json.loads(o["alternative_game_ids"]) if o["alternative_game_ids"] else []):
            conn.execute(
                "UPDATE orphan_reviews SET alternative_game_ids = ? WHERE id = ?",
                (json.dumps(alt_ids) if alt_ids else None, o["id"]),
            )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


def _cover_url(filename):
    """Cover art URL with a cache-busting parameter: since the filename is
    stable (based on the game's title/id), replacing one cover with another
    would otherwise produce the same URL, and the browser would keep showing
    the old cached image instead of the new one."""
    return f"/api/covers/{filename}?v={int(time.time() * 1000)}"


@app.route("/api/games/<int:game_id>/cover", methods=["POST"])
def upload_cover(game_id):
    f = request.files.get("cover")
    if not f or not f.filename:
        return jsonify({"error": "no_image"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in cover_search.IMAGE_EXTENSIONS:
        return jsonify({"error": "unsupported_format"}), 400
    content = f.read()
    if not cover_search.is_valid_image(content):
        return jsonify({"error": "invalid_image"}), 400
    game = conn_fetch_one("SELECT title FROM games WHERE id = ?", (game_id,))
    filename = cover_search.safe_title_filename(game["title"] if game else "jeu", game_id, ext)
    path = COVERS_DIR / filename
    path.write_bytes(content)
    cover_path = _cover_url(filename)
    conn = get_conn()
    conn.execute("UPDATE games SET cover_path = ? WHERE id = ?", (cover_path, game_id))
    conn.commit()
    conn.close()
    return jsonify({"cover_path": cover_path})


def conn_fetch_one(sql, params=()):
    conn = get_conn()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return row


@app.route("/api/covers/<path:filename>")
def get_cover(filename):
    # cover_path is always stored as "/api/covers/<file>?v=<timestamp>" (see
    # _cover_url below) and that query param changes every single time the
    # cover is replaced — so this exact URL can never point at stale
    # content. "no-cache" was forcing a conditional-GET round trip for
    # every cover thumbnail on every grid render for no benefit; a long,
    # immutable cache lets the browser skip the network entirely on repeat
    # views (switching tabs, reopening the app, ...).
    resp = send_from_directory(COVERS_DIR, filename)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@app.route("/api/cover-art-preview/<path:filename>")
def cover_art_preview(filename):
    return send_from_directory(cover_search.COVER_ART_DIR, filename)


# ----------------------------------------------------------------- Orphan reviews
@app.route("/api/orphan-reviews", methods=["GET"])
def orphan_reviews():
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.*, g.title AS suggested_title
           FROM orphan_reviews o LEFT JOIN games g ON g.id = o.suggested_game_id
           WHERE o.linked_game_id IS NULL"""
    ).fetchall()

    # Batch-resolve every alternative's title in one query instead of one
    # SELECT per alternative per row — the orphan list is small, but no
    # reason to pay N+1 round-trips for something this cheap to batch.
    parsed_alt_ids = []
    all_alt_ids = set()
    for r in rows:
        ids = json.loads(r["alternative_game_ids"]) if r["alternative_game_ids"] else []
        parsed_alt_ids.append(ids)
        all_alt_ids.update(ids)

    titles_by_id = {}
    if all_alt_ids:
        placeholders = ", ".join("?" for _ in all_alt_ids)
        for g in conn.execute(f"SELECT id, title FROM games WHERE id IN ({placeholders})", list(all_alt_ids)):
            titles_by_id[g["id"]] = g["title"]
    conn.close()

    result = []
    for r, ids in zip(rows, parsed_alt_ids):
        d = _row_to_dict(r)
        d["alternatives"] = [{"id": gid, "title": titles_by_id[gid]} for gid in ids if gid in titles_by_id]
        result.append(d)
    return jsonify(result)


@app.route("/api/orphan-reviews/<int:orphan_id>/link", methods=["POST"])
def link_orphan_review(orphan_id):
    data = request.get_json(force=True)
    game_id = data.get("game_id")
    conn = get_conn()
    orphan = conn.execute("SELECT * FROM orphan_reviews WHERE id = ?", (orphan_id,)).fetchone()
    if not orphan:
        conn.close()
        return jsonify({"error": "not_found"}), 404
    target_game = conn.execute("SELECT id FROM games WHERE id = ?", (game_id,)).fetchone()
    if not target_game:
        conn.close()
        return jsonify({"error": "target_game_not_found"}), 404
    conn.execute("UPDATE games SET review = ? WHERE id = ?", (orphan["review"], game_id))
    conn.execute("UPDATE orphan_reviews SET linked_game_id = ? WHERE id = ?", (game_id, orphan_id))
    conn.commit()
    conn.close()
    applog.info(f"Orphan review confirmed and linked (orphan #{orphan_id} -> game #{game_id}).")
    return jsonify({"ok": True})


@app.route("/api/orphan-reviews/<int:orphan_id>/dismiss", methods=["POST"])
def dismiss_orphan_review(orphan_id):
    """Marks an orphan review as handled without linking it to any game —
    used when the user confirms the suggestion is wrong (or there's no
    match) and doesn't want to see it flagged anymore. The review text
    itself is preserved, not deleted, in case they want to add it manually
    to a game later."""
    conn = get_conn()
    orphan = conn.execute("SELECT id FROM orphan_reviews WHERE id = ?", (orphan_id,)).fetchone()
    if not orphan:
        conn.close()
        return jsonify({"error": "not_found"}), 404
    conn.execute("UPDATE orphan_reviews SET linked_game_id = -1 WHERE id = ?", (orphan_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Backlog/Completed duplicates
@app.route("/api/duplicates", methods=["GET"])
def list_duplicates():
    """Live-computed, never cached: a game showing up here means it
    currently exists in both Backlog and Completed under the same
    (normalized) title. Resolving it — deleting one copy, or renaming one so
    they no longer match — makes it disappear on its own next time this is
    called."""
    return jsonify(dup_mgr.find_duplicates())


# ----------------------------------------------------------------- Sanitize Game Names
@app.route("/api/sanitize/scan", methods=["POST"])
def sanitize_scan():
    data = request.get_json(force=True) or {}
    allow_external = bool(data.get("allow_external", True))
    started = sanitize_mgr.start_scan(allow_external=allow_external)
    if not started:
        return jsonify({"error": "scan_already_running"}), 409
    applog.info("Sanitize Game Names scan started.")
    return jsonify({"ok": True})


@app.route("/api/sanitize/status", methods=["GET"])
def sanitize_status():
    return jsonify(sanitize_mgr.get_scan_status())


@app.route("/api/sanitize/cancel", methods=["POST"])
def sanitize_cancel():
    sanitize_mgr.cancel_scan()
    return jsonify({"ok": True})


@app.route("/api/sanitize/pending", methods=["GET"])
def sanitize_pending():
    return jsonify(sanitize_mgr.list_pending())


@app.route("/api/sanitize/<int:game_id>/accept", methods=["POST"])
def sanitize_accept(game_id):
    ok = sanitize_mgr.accept_suggestion(game_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    applog.info(f"Name sanitized for game #{game_id}.")
    return jsonify({"ok": True})


@app.route("/api/sanitize/<int:game_id>/reject", methods=["POST"])
def sanitize_reject(game_id):
    ok = sanitize_mgr.reject_suggestion(game_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


@app.route("/api/sanitize/dismiss-first-scan-notice", methods=["POST"])
def sanitize_dismiss_notice():
    cfg = load_config()
    cfg["cover_scan_notice_dismissed"] = True
    save_config(cfg)
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Settings
@app.route("/api/settings")
def get_settings():
    cfg = load_config()
    return jsonify({
        "data_dir": str(DATA_DIR),
        "backup_dir": str(backup_mgr.BACKUP_DIR),
        "nb_backups": len(backup_mgr.list_backups()),
        "player_name": cfg.get("player_name", ""),
        "rawg_api_key": cfg.get("rawg_api_key", ""),
        "giantbomb_api_key": cfg.get("giantbomb_api_key", ""),
        "steamgriddb_api_key": cfg.get("steamgriddb_api_key", ""),
        "thegamesdb_api_key": cfg.get("thegamesdb_api_key", ""),
        "internet_search_consent": bool(cfg.get("internet_search_consent", False)),
        "cover_scan_notice_dismissed": bool(cfg.get("cover_scan_notice_dismissed", False)),
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(force=True)
    cfg = load_config()
    if "player_name" in data:
        cfg["player_name"] = (data["player_name"] or "").strip()
    if "rawg_api_key" in data:
        cfg["rawg_api_key"] = (data["rawg_api_key"] or "").strip()
    if "giantbomb_api_key" in data:
        cfg["giantbomb_api_key"] = (data["giantbomb_api_key"] or "").strip()
    if "steamgriddb_api_key" in data:
        cfg["steamgriddb_api_key"] = (data["steamgriddb_api_key"] or "").strip()
    if "thegamesdb_api_key" in data:
        cfg["thegamesdb_api_key"] = (data["thegamesdb_api_key"] or "").strip()
    if "internet_search_consent" in data:
        cfg["internet_search_consent"] = bool(data["internet_search_consent"])
    save_config(cfg)
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Cover art search
@app.route("/api/cover-search")
def cover_search_route():
    title = request.args.get("title", "")
    cfg = load_config()
    return jsonify(cover_search.search_with_local(
        title, rawg_api_key=cfg.get("rawg_api_key"),
        giantbomb_api_key=cfg.get("giantbomb_api_key"),
        steamgriddb_api_key=cfg.get("steamgriddb_api_key"),
        thegamesdb_api_key=cfg.get("thegamesdb_api_key"),
    ))


@app.route("/api/cover-proxy")
def cover_proxy():
    """Fetches a cover-art candidate from a third-party URL and streams it
    back same-origin. The cover editor loads images into a <canvas> for
    interactive cropping and then exports pixel data from it — a canvas
    fed directly from a cross-origin image without permissive CORS headers
    becomes 'tainted' and silently refuses to export, so every source the
    editor can open has to come back through our own origin first.

    The actual fetch (and its SSRF guard, rejecting anything that isn't a
    plain http(s) URL resolving to a public IP) lives in
    backend.covers.fetch_proxied_image, shared with every other cover
    download path rather than duplicated here."""
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url_required"}), 400
    result = cover_search.fetch_proxied_image(url)
    if result is None:
        return jsonify({"error": "download_failed"}), 502
    content, content_type = result
    return Response(content, mimetype=content_type, headers={"Cache-Control": "no-cache"})


@app.route("/api/games/<int:game_id>/cover-from-url", methods=["POST"])
def set_cover_from_url(game_id):
    data = request.get_json(force=True)
    url = data.get("url")
    if not url:
        return jsonify({"error": "url_required"}), 400
    game = conn_fetch_one("SELECT title FROM games WHERE id = ?", (game_id,))
    base = COVERS_DIR / cover_search.safe_title_filename(game["title"] if game else "jeu", game_id, "")
    dest = cover_search.download_image_with_detected_ext(url, base)
    if not dest:
        return jsonify({"error": "download_failed"}), 502
    cover_path = _cover_url(dest.name)
    conn = get_conn()
    conn.execute("UPDATE games SET cover_path = ? WHERE id = ?", (cover_path, game_id))
    conn.commit()
    conn.close()
    return jsonify({"cover_path": cover_path})


@app.route("/api/games/<int:game_id>/cover-from-local", methods=["POST"])
def set_cover_from_local(game_id):
    """Uses an image found in the cover_art/ folder (chosen by the user, or
    auto-detected by name match)."""
    data = request.get_json(force=True)
    filename_in = data.get("filename")
    if not filename_in or "/" in filename_in or ".." in filename_in:
        return jsonify({"error": "invalid_filename"}), 400
    src = cover_search.COVER_ART_DIR / filename_in
    if not src.exists():
        return jsonify({"error": "cover_art_not_found"}), 404
    if not cover_search.is_valid_image(src):
        return jsonify({"error": "invalid_image"}), 400
    game = conn_fetch_one("SELECT title FROM games WHERE id = ?", (game_id,))
    filename = cover_search.safe_title_filename(game["title"] if game else "jeu", game_id, src.suffix.lower())
    dest = COVERS_DIR / filename
    dest.write_bytes(src.read_bytes())
    cover_path = _cover_url(filename)
    conn = get_conn()
    conn.execute("UPDATE games SET cover_path = ? WHERE id = ?", (cover_path, game_id))
    conn.commit()
    conn.close()
    return jsonify({"cover_path": cover_path})


@app.route("/api/covers/bulk-fill", methods=["POST"])
def bulk_fill_covers():
    started = cover_search.start_bulk_fill()
    return jsonify({"started": started, "status": cover_search.get_bulk_status()})


@app.route("/api/covers/bulk-fill/status")
def bulk_fill_status():
    return jsonify(cover_search.get_bulk_status())


@app.route("/api/covers/bulk-fill/cancel", methods=["POST"])
def bulk_fill_cancel():
    cover_search.cancel_bulk_fill()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Backups
@app.route("/api/backups", methods=["GET"])
def get_backups():
    return jsonify(backup_mgr.list_backups())


@app.route("/api/backups", methods=["POST"])
def make_backup():
    name = backup_mgr.create_backup(reason="manual")
    return jsonify({"created": name})


@app.route("/api/backups/<path:name>/restore", methods=["POST"])
def restore_backup_route(name):
    ok = backup_mgr.restore_backup(name)
    if not ok:
        return jsonify({"error": "backup_not_found"}), 404
    return jsonify({"ok": True})


# ----------------------------------------------------------------- Stats
@app.route("/api/stats")
def stats():
    year = request.args.get("year")
    return jsonify(compute_stats(year=int(year) if year else None))


@app.route("/api/year-review/years")
def year_review_years():
    return jsonify(list_review_years())


@app.route("/api/year-review")
def year_review():
    year = request.args.get("year")
    if not year:
        return jsonify({"error": "year_required"}), 400
    result = build_year_review(int(year))
    if result is None:
        return jsonify({"error": "no_games_year"}), 404
    return jsonify(result)


# ----------------------------------------------------------------- Export
@app.route("/api/export/xlsx")
def export_xlsx():
    data = exporter.export_xlsx()
    from io import BytesIO
    applog.info("Exported My_Backlog.xlsx (data + settings).")
    return send_file(BytesIO(data), as_attachment=True, download_name="My_Backlog.xlsx",
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/export/csv")
def export_csv():
    data = exporter.export_csv_zip()
    from io import BytesIO
    applog.info("Exported My_Backlog_csv.zip (data + settings).")
    return send_file(BytesIO(data), as_attachment=True, download_name="My_Backlog_csv.zip",
                      mimetype="application/zip")


@app.route("/api/export/covers")
def export_covers():
    data = exporter.export_covers_zip()
    from io import BytesIO
    applog.info("Exported cover art collection (My_Backlog_covers.zip).")
    return send_file(BytesIO(data), as_attachment=True, download_name="My_Backlog_covers.zip",
                      mimetype="application/zip")


# ----------------------------------------------------------------- Shutdown
def _terminate_process():
    """The actual process-exit call, split out so tests can monkeypatch it
    without killing the test runner."""
    os._exit(0)


@app.route("/api/shutdown", methods=["POST"])
def shutdown_app():
    """Cleanly shuts the application down from the UI's red "Close
    Application" button, so the user never has to go find and close the
    terminal window manually. Ctrl+C in the terminal keeps working too —
    this just calls the same process-exit path."""
    applog.info("Shutdown requested from the web UI.")

    def _do_shutdown():
        time.sleep(0.3)  # give the response time to reach the browser first
        _terminate_process()

    threading.Thread(target=_do_shutdown, daemon=True).start()
    return jsonify({"ok": True})


@app.errorhandler(Exception)
def handle_uncaught_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    applog.error(f"Unhandled error on {request.method} {request.path}: {e}")
    return jsonify({"error": "internal_error"}), 500


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    allow_lan = app.config["BACKLOG_ALLOW_LAN"]
    # Localhost-only by default: this app has no login/authentication of
    # any kind, so binding 0.0.0.0 would let any other device on the same
    # network read, edit, or delete the whole backlog. BACKLOG_ALLOW_LAN=1
    # opts into that explicitly (e.g. to also use it from a phone on the
    # same Wi-Fi). Inside Docker this is set for you (see Dockerfile) since
    # the container's own loopback isn't reachable from the host anyway —
    # the actual exposure there is controlled by the docker-compose port
    # mapping instead.
    host = "0.0.0.0" if allow_lan else "127.0.0.1"
    # Always show/open 127.0.0.1 for the local user, even when also
    # listening on 0.0.0.0 for other devices — "http://0.0.0.0:5000" isn't
    # a meaningful URL to open in a browser.
    url = f"http://127.0.0.1:{port}"
    if os.environ.get("BACKLOG_NO_BROWSER") != "1":
        threading.Timer(1.0, _open_browser).start()
    applog.startup_banner(url)
    if allow_lan:
        applog.warn(
            "BACKLOG_ALLOW_LAN=1: listening on all network interfaces. "
            "Anyone on your network can reach this app — only enable this "
            "on networks you trust."
        )
    try:
        # threaded=True so a slow outbound call (HowLongToBeat lookup,
        # cover-art search) doesn't freeze the whole UI for the duration —
        # Werkzeug's dev server is single-threaded by default, so without
        # this every other request queues behind whichever one is
        # currently waiting on a third-party API.
        app.run(host=host, port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        applog.shutdown()
