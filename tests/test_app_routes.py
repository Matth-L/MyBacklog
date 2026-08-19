import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Démarre l'app Flask avec des dossiers de données isolés dans un tmp_path,
    et retourne un client de test."""
    monkeypatch.setenv("BACKLOG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BACKLOG_BACKUP_DIR", str(tmp_path / "backup_backlog"))
    monkeypatch.setenv("BACKLOG_COVER_ART_DIR", str(tmp_path / "cover_art"))
    monkeypatch.setenv("BACKLOG_NO_BROWSER", "1")
    for mod in list(sys.modules):
        if mod.startswith("backend") or mod == "app":
            del sys.modules[mod]
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_create_game_directly_as_completed_defaults_available_to_owned(client):
    res = client.post("/api/games", json={"title": "Jeu direct", "status": "completed"})
    assert res.status_code == 201
    assert res.get_json()["available"] == 1


def test_create_game_as_completed_respects_explicit_available(client):
    res = client.post("/api/games", json={"title": "Jeu explicite", "status": "completed", "available": 0})
    assert res.status_code == 201
    assert res.get_json()["available"] == 0


def test_create_backlog_game_does_not_default_available(client):
    res = client.post("/api/games", json={"title": "Jeu backlog"})
    assert res.status_code == 201
    assert res.get_json()["available"] is None


def test_switching_backlog_to_completed_defaults_available_to_owned(client):
    created = client.post("/api/games", json={"title": "A finir"}).get_json()
    updated = client.put(f"/api/games/{created['id']}", json={"status": "completed"})
    assert updated.get_json()["available"] == 1


def test_switching_backlog_to_completed_respects_explicit_available(client):
    created = client.post("/api/games", json={"title": "A finir sans le posseder"}).get_json()
    updated = client.put(f"/api/games/{created['id']}", json={"status": "completed", "available": 0})
    assert updated.get_json()["available"] == 0


def test_updating_an_already_completed_game_never_re_forces_available(client):
    """Une fois le jeu déjà fini, on ne revérifie/reforce plus jamais la
    possession sur les mises à jour suivantes (même sans champ 'available')."""
    created = client.post("/api/games", json={"title": "Deja fini", "status": "completed"}).get_json()
    assert created["available"] == 1

    # L'utilisateur repasse explicitement à Non...
    client.put(f"/api/games/{created['id']}", json={"available": 0})
    # ... puis fait une autre modification quelconque, sans toucher à available :
    # la valeur ne doit surtout pas être re-forcée à 1.
    updated = client.put(f"/api/games/{created['id']}", json={"hours_played": 12})
    assert updated.get_json()["available"] == 0


def _make_test_image_bytes():
    import io
    import random
    from PIL import Image
    img = Image.new("RGB", (60, 60))
    img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(3600)])
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_replacing_a_cover_produces_a_different_url_to_bust_the_browser_cache(client):
    """Bug corrigé : le nom de fichier d'une jaquette est stable (basé sur le
    titre/id du jeu), donc remplacer une jaquette par une autre produisait la
    même URL et le navigateur affichait l'ancienne image mise en cache. Un
    paramètre de version doit rendre chaque nouvelle jaquette unique."""
    from io import BytesIO
    game = client.post("/api/games", json={"title": "Jeu jaquette", "status": "completed"}).get_json()

    img1 = (BytesIO(_make_test_image_bytes()), "cover1.jpg")
    res1 = client.post(f"/api/games/{game['id']}/cover", data={"cover": img1}, content_type="multipart/form-data")
    cover_path_1 = res1.get_json()["cover_path"]

    img2 = (BytesIO(_make_test_image_bytes()), "cover2.jpg")
    res2 = client.post(f"/api/games/{game['id']}/cover", data={"cover": img2}, content_type="multipart/form-data")
    cover_path_2 = res2.get_json()["cover_path"]

    assert cover_path_1 != cover_path_2
    assert "?v=" in cover_path_1
    assert "?v=" in cover_path_2
    # même chemin de fichier de base (même titre/id), seul le paramètre change
    assert cover_path_1.split("?")[0] == cover_path_2.split("?")[0]


def test_cover_endpoint_sends_long_lived_immutable_cache_header(client):
    """cover_path always carries a fresh ?v=<timestamp> (see _cover_url), so
    the exact URL returned here can never point at stale content — safe (and
    much cheaper, especially over a full grid of thumbnails) to cache
    aggressively instead of forcing a revalidation round trip every time."""
    from io import BytesIO
    game = client.post("/api/games", json={"title": "Jeu cache", "status": "completed"}).get_json()
    img = (BytesIO(_make_test_image_bytes()), "cover.jpg")
    res = client.post(f"/api/games/{game['id']}/cover", data={"cover": img}, content_type="multipart/form-data")
    cover_path = res.get_json()["cover_path"]
    assert "?v=" in cover_path
    cover_res = client.get(cover_path)
    assert cover_res.headers.get("Cache-Control") == "public, max-age=31536000, immutable"


def test_json_responses_are_gzip_compressed_when_client_accepts_it(client):
    client.post("/api/games", json={"title": "Compression Test", "status": "backlog", "notes": "x" * 2000})
    res = client.get("/api/games", headers={"Accept-Encoding": "gzip"})
    assert res.headers.get("Content-Encoding") == "gzip"
    assert res.headers.get("Vary") == "Accept-Encoding"
    import gzip as gzip_module
    decoded = gzip_module.decompress(res.data)
    assert b"Compression Test" in decoded


def test_json_responses_are_not_compressed_without_accept_encoding(client):
    res = client.get("/api/games")
    assert res.headers.get("Content-Encoding") is None


# ------------------------------------------------------------- Orphan reviews (import validation)

def test_orphan_reviews_endpoint_includes_suggested_title(client):
    game = client.post("/api/games", json={"title": "Nier Automata", "status": "completed"}).get_json()
    import app as app_module
    conn = app_module.get_conn()
    conn.execute(
        "INSERT INTO orphan_reviews (original_title, review, suggested_game_id, match_type) VALUES (?, ?, ?, ?)",
        ("Nier Automata Ending A", "Great game", game["id"], "fuzzy"),
    )
    conn.commit()
    conn.close()

    res = client.get("/api/orphan-reviews")
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["suggested_title"] == "Nier Automata"
    assert data[0]["match_type"] == "fuzzy"


def test_orphan_review_link_applies_review_and_removes_from_list(client):
    game = client.post("/api/games", json={"title": "Hades", "status": "completed"}).get_json()
    import app as app_module
    conn = app_module.get_conn()
    conn.execute(
        "INSERT INTO orphan_reviews (original_title, review, suggested_game_id, match_type) VALUES (?, ?, ?, ?)",
        ("Hades (roguelike)", "So good", game["id"], "substring"),
    )
    conn.commit()
    orphan_id = conn.execute("SELECT id FROM orphan_reviews").fetchone()["id"]
    conn.close()

    res = client.post(f"/api/orphan-reviews/{orphan_id}/link", json={"game_id": game["id"]})
    assert res.status_code == 200

    updated_game = client.get(f"/api/games/{game['id']}").get_json()
    assert updated_game["review"] == "So good"

    remaining = client.get("/api/orphan-reviews").get_json()
    assert remaining == []


def test_orphan_review_dismiss_removes_from_list_without_linking(client):
    client.post("/api/games", json={"title": "Some Game", "status": "completed"})
    import app as app_module
    conn = app_module.get_conn()
    conn.execute(
        "INSERT INTO orphan_reviews (original_title, review) VALUES (?, ?)",
        ("Truly Unmatched Title", "A review"),
    )
    conn.commit()
    orphan_id = conn.execute("SELECT id FROM orphan_reviews").fetchone()["id"]
    conn.close()

    res = client.post(f"/api/orphan-reviews/{orphan_id}/dismiss")
    assert res.status_code == 200

    remaining = client.get("/api/orphan-reviews").get_json()
    assert remaining == []

    game = client.get("/api/games?status=completed").get_json()[0]
    assert game["review"] is None  # dismissing never touches game data


# ------------------------------------------------------------- DLC / abandoned filters

def test_games_endpoint_filters_by_dlc(client):
    client.post("/api/games", json={"title": "Base Game", "status": "backlog", "dlc": 0})
    client.post("/api/games", json={"title": "Some DLC", "status": "backlog", "dlc": 1})

    only_dlc = client.get("/api/games?dlc=1").get_json()
    assert [g["title"] for g in only_dlc] == ["Some DLC"]

    hide_dlc = client.get("/api/games?dlc=0").get_json()
    assert [g["title"] for g in hide_dlc] == ["Base Game"]

    all_games = client.get("/api/games").get_json()
    assert len(all_games) == 2


def test_games_endpoint_filters_by_abandoned(client):
    client.post("/api/games", json={"title": "Finished Game", "status": "completed", "abandoned": 0})
    client.post("/api/games", json={"title": "Gave Up Game", "status": "completed", "abandoned": 1})

    only_abandoned = client.get("/api/games?abandoned=1").get_json()
    assert [g["title"] for g in only_abandoned] == ["Gave Up Game"]

    hide_abandoned = client.get("/api/games?abandoned=0").get_json()
    assert [g["title"] for g in hide_abandoned] == ["Finished Game"]

    all_games = client.get("/api/games").get_json()
    assert len(all_games) == 2


def test_games_endpoint_combines_dlc_and_abandoned_filters(client):
    client.post("/api/games", json={"title": "A", "status": "backlog", "dlc": 1, "abandoned": 0})
    client.post("/api/games", json={"title": "B", "status": "backlog", "dlc": 1, "abandoned": 1})
    client.post("/api/games", json={"title": "C", "status": "backlog", "dlc": 0, "abandoned": 1})

    res = client.get("/api/games?dlc=1&abandoned=1").get_json()
    assert [g["title"] for g in res] == ["B"]


# ------------------------------------------------------------- Backlog/Completed duplicate detection

def test_create_game_blocks_duplicate_across_statuses(client):
    client.post("/api/games", json={"title": "Hades", "status": "completed"})
    res = client.post("/api/games", json={"title": "Hades", "status": "backlog"})
    assert res.status_code == 409
    body = res.get_json()
    assert body["error"] == "duplicate"
    assert body["conflict"]["status"] == "completed"

    # never silently created
    all_games = client.get("/api/games").get_json()
    assert len(all_games) == 1


def test_create_game_duplicate_check_is_normalized(client):
    """Case/spacing/accents differences still count as the same title."""
    client.post("/api/games", json={"title": "Pokémon Rouge", "status": "backlog"})
    res = client.post("/api/games", json={"title": "  pokemon   rouge ", "status": "completed"})
    assert res.status_code == 409


def test_create_game_allows_duplicate_with_force_flag(client):
    client.post("/api/games", json={"title": "Hades", "status": "completed"})
    res = client.post("/api/games", json={"title": "Hades", "status": "backlog", "force_duplicate": True})
    assert res.status_code == 201

    all_games = client.get("/api/games").get_json()
    assert len(all_games) == 2


def test_create_game_does_not_conflict_with_same_status(client):
    """Two backlog entries with similar titles aren't a backlog/completed
    conflict — only cross-status duplicates are flagged."""
    client.post("/api/games", json={"title": "Hades", "status": "backlog"})
    res = client.post("/api/games", json={"title": "Hades", "status": "backlog"})
    assert res.status_code == 201


def test_update_game_status_change_blocks_duplicate(client):
    """Two backlog entries sharing a title are allowed on their own (only
    cross-status duplicates are blocked at creation time) — but moving one
    of them to 'completed' would create a genuine new backlog+completed
    split against the other, and that must be flagged."""
    a = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()
    b = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()
    assert a["id"] != b["id"]

    res = client.put(f"/api/games/{b['id']}", json={"status": "completed"})
    assert res.status_code == 409
    assert res.get_json()["conflict"]["id"] == a["id"]
    assert res.get_json()["conflict"]["status"] == "backlog"

    # status was not changed
    game = client.get(f"/api/games/{b['id']}").get_json()
    assert game["status"] == "backlog"


def test_update_game_status_change_allowed_with_force_flag(client):
    a = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()
    b = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()

    res = client.put(f"/api/games/{b['id']}", json={"status": "completed", "force_duplicate": True})
    assert res.status_code == 200
    assert res.get_json()["status"] == "completed"


def test_update_game_does_not_conflict_check_on_routine_edits(client):
    """A plain field edit (e.g. review text) that happens to include the
    current status in the payload — as the frontend always does — must not
    trigger a duplicate check at all, since status isn't actually changing."""
    a = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()
    client.post("/api/games", json={"title": "Celeste", "status": "backlog"})

    # Same status as already stored ("backlog") — not a transition, even
    # though another same-title backlog row exists.
    res = client.put(f"/api/games/{a['id']}", json={"status": "backlog", "notes": "just a note"})
    assert res.status_code == 200
    assert res.get_json()["notes"] == "just a note"


def test_duplicates_endpoint_lists_current_conflicts(client):
    client.post("/api/games", json={"title": "Hades", "status": "completed"})
    client.post("/api/games", json={"title": "Hades", "status": "backlog", "force_duplicate": True})
    client.post("/api/games", json={"title": "Unique Game", "status": "backlog"})

    res = client.get("/api/duplicates").get_json()
    assert len(res) == 1
    assert res[0]["backlog_title"] == "Hades"
    assert res[0]["completed_title"] == "Hades"


def test_duplicates_endpoint_self_heals_after_deletion(client):
    client.post("/api/games", json={"title": "Hades", "status": "completed"})
    backlog_res = client.post("/api/games", json={"title": "Hades", "status": "backlog", "force_duplicate": True})
    backlog_id = backlog_res.get_json()["id"]

    assert len(client.get("/api/duplicates").get_json()) == 1

    client.delete(f"/api/games/{backlog_id}")
    assert client.get("/api/duplicates").get_json() == []


def test_session_import_reports_duplicates_found(client, tmp_path):
    """The 'import a new Excel/session at any time' flow (Phase 1) should
    also surface backlog/completed duplicates found in the imported file,
    same as the initial setup import does."""
    import pandas as pd
    from backend import exporter as exporter_module

    # Seed a completed + a backlog game sharing a title, export that as the
    # file to (re-)import, so the exported file itself contains the
    # duplicate pair.
    client.post("/api/games", json={"title": "Hades", "status": "completed"})
    client.post("/api/games", json={"title": "Hades", "status": "backlog", "force_duplicate": True})

    xlsx_path = tmp_path / "dup_session.xlsx"
    xlsx_path.write_bytes(exporter_module.export_xlsx())

    res = client.post("/api/session/import", json={"path": str(xlsx_path)})
    assert res.status_code == 200
    assert res.get_json()["summary"]["duplicates_found"] == 1


# ------------------------------------------------------------- Session import via file picker (not a typed path)

def test_session_import_file_accepts_uploaded_xlsx(client):
    """The Settings UI now offers a real file picker instead of asking the
    user to type a filesystem path — this is the endpoint it calls."""
    from backend import exporter as exporter_module
    from io import BytesIO

    client.post("/api/games", json={"title": "Old Game", "status": "backlog"})

    xlsx_bytes = exporter_module.export_xlsx()  # a valid session file to re-import
    res = client.post(
        "/api/session/import-file",
        data={"file": (BytesIO(xlsx_bytes), "my_session.xlsx")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert res.get_json()["ok"] is True


def test_session_import_file_rejects_missing_file(client):
    res = client.post("/api/session/import-file", data={}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_session_import_file_rejects_unsupported_extension(client):
    from io import BytesIO

    res = client.post(
        "/api/session/import-file",
        data={"file": (BytesIO(b"not a real file"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_session_import_file_cleans_up_temp_file(client):
    """The uploaded file is written to a temp dir to be read by the
    importer — it must not be left behind afterwards."""
    from backend import exporter as exporter_module
    from io import BytesIO
    import app as app_module

    xlsx_bytes = exporter_module.export_xlsx()
    client.post(
        "/api/session/import-file",
        data={"file": (BytesIO(xlsx_bytes), "cleanup_test.xlsx")},
        content_type="multipart/form-data",
    )
    assert not (app_module.UPLOAD_TMP / "cleanup_test.xlsx").exists()


# ------------------------------------------------------------- Data integrity: rename never breaks review linkage

def test_renaming_a_game_preserves_its_review():
    """Reviews are stored on the game's own row (linked by stable id), not
    re-matched by title after the fact — renaming must never disconnect
    the review."""
    import sys
    for mod in list(sys.modules):
        if mod.startswith("backend") or mod == "app":
            del sys.modules[mod]
    import tempfile as _tempfile
    with _tempfile.TemporaryDirectory() as tmp:
        import os as _os
        _os.environ["BACKLOG_DATA_DIR"] = tmp
        import app as app_module
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            res = c.post("/api/games", json={"title": "Typo Title", "status": "completed"})
            game_id = res.get_json()["id"]
            c.put(f"/api/games/{game_id}", json={"review": "Loved it"})

            c.put(f"/api/games/{game_id}", json={"title": "Corrected Title"})

            game = c.get(f"/api/games/{game_id}").get_json()
            assert game["title"] == "Corrected Title"
            assert game["review"] == "Loved it"
            assert game["id"] == game_id  # same stable id throughout


# ------------------------------------------------------------- Title editing (regression)

def test_existing_game_title_can_be_edited(client):
    """Titles must remain editable after creation (regression: the modal's
    title field was previously locked to read-only for existing games)."""
    res = client.post("/api/games", json={"title": "Original Title", "status": "backlog"})
    game_id = res.get_json()["id"]

    res = client.put(f"/api/games/{game_id}", json={"title": "Corrected Title"})
    assert res.status_code == 200
    assert res.get_json()["title"] == "Corrected Title"

    res = client.get(f"/api/games/{game_id}")
    assert res.get_json()["title"] == "Corrected Title"


# ------------------------------------------------------------- Export covers / shutdown (persistent controls)

def test_export_covers_returns_zip_of_cover_files(client):
    import app as app_module
    from PIL import Image
    import io as _io

    # Drop two "cover" files directly in the covers dir.
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    (app_module.COVERS_DIR / "game_1.png").write_bytes(buf.getvalue())
    (app_module.COVERS_DIR / "game_2.png").write_bytes(buf.getvalue())

    res = client.get("/api/export/covers")
    assert res.status_code == 200
    assert res.mimetype == "application/zip"

    import zipfile
    zf = zipfile.ZipFile(_io.BytesIO(res.data))
    names = zf.namelist()
    assert "game_1.png" in names
    assert "game_2.png" in names


def test_export_covers_handles_empty_covers_dir(client):
    res = client.get("/api/export/covers")
    assert res.status_code == 200
    import zipfile, io as _io
    zf = zipfile.ZipFile(_io.BytesIO(res.data))
    assert zf.namelist() == []


def test_shutdown_endpoint_returns_ok_and_calls_terminate(client, monkeypatch):
    import app as app_module

    called = {"n": 0}
    monkeypatch.setattr(app_module, "_terminate_process", lambda: called.__setitem__("n", called["n"] + 1))

    res = client.post("/api/shutdown")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # The actual process-exit call happens on a short delay in a background
    # thread — wait briefly and confirm it was invoked (not the real exit).
    import time as _time
    for _ in range(20):
        if called["n"] > 0:
            break
        _time.sleep(0.05)
    assert called["n"] == 1


# ------------------------------------------------------------- Sanitize Game Names (routes)

def test_sanitize_scan_endpoint_and_pending_list(client):
    client.post("/api/games", json={"title": "Ni no Kuni", "status": "backlog"})

    res = client.post("/api/sanitize/scan", json={"allow_external": False})
    assert res.status_code == 200

    import time
    for _ in range(50):
        status = client.get("/api/sanitize/status").get_json()
        if not status["running"]:
            break
        time.sleep(0.05)

    pending = client.get("/api/sanitize/pending").get_json()
    assert len(pending) == 1
    assert pending[0]["suggested_name"] == "Ni no Kuni: Wrath of the White Witch"


def test_sanitize_scan_refuses_concurrent_scans(client):
    client.post("/api/games", json={"title": "Ni no Kuni", "status": "backlog"})
    res1 = client.post("/api/sanitize/scan", json={"allow_external": False})
    assert res1.status_code == 200
    res2 = client.post("/api/sanitize/scan", json={"allow_external": False})
    assert res2.status_code == 409

    import time
    for _ in range(50):
        if not client.get("/api/sanitize/status").get_json()["running"]:
            break
        time.sleep(0.05)


def test_sanitize_accept_endpoint_renames_game(client):
    game = client.post("/api/games", json={"title": "Ni no Kuni", "status": "backlog"}).get_json()
    client.post("/api/sanitize/scan", json={"allow_external": False})
    import time
    for _ in range(50):
        if not client.get("/api/sanitize/status").get_json()["running"]:
            break
        time.sleep(0.05)

    res = client.post(f"/api/sanitize/{game['id']}/accept")
    assert res.status_code == 200

    updated = client.get(f"/api/games/{game['id']}").get_json()
    assert updated["title"] == "Ni no Kuni: Wrath of the White Witch"
    assert updated["id"] == game["id"]

    pending = client.get("/api/sanitize/pending").get_json()
    assert pending == []


def test_sanitize_reject_endpoint_keeps_title(client):
    game = client.post("/api/games", json={"title": "Ni no Kuni", "status": "backlog"}).get_json()
    client.post("/api/sanitize/scan", json={"allow_external": False})
    import time
    for _ in range(50):
        if not client.get("/api/sanitize/status").get_json()["running"]:
            break
        time.sleep(0.05)

    res = client.post(f"/api/sanitize/{game['id']}/reject")
    assert res.status_code == 200

    updated = client.get(f"/api/games/{game['id']}").get_json()
    assert updated["title"] == "Ni no Kuni"

    pending = client.get("/api/sanitize/pending").get_json()
    assert pending == []


def test_sanitize_accept_returns_404_for_unknown_game(client):
    res = client.post("/api/sanitize/99999/accept")
    assert res.status_code == 404


def test_cover_scan_notice_dismissal_persists(client):
    settings = client.get("/api/settings").get_json()
    assert settings["cover_scan_notice_dismissed"] is False

    res = client.post("/api/sanitize/dismiss-first-scan-notice")
    assert res.status_code == 200

    settings = client.get("/api/settings").get_json()
    assert settings["cover_scan_notice_dismissed"] is True


# ------------------------------------------------------------- Changing an existing cover (regression)

def test_cover_from_url_can_replace_an_existing_cover(client, monkeypatch):
    """A game that already has a cover must still be changeable via a new
    search result — this is what the frontend's cover-search 'use this
    cover' click ultimately calls."""
    import app as app_module
    from pathlib import Path
    from PIL import Image
    import io as _io

    def fake_download(url, base_path):
        color = (255, 0, 0) if "first" in url else (0, 255, 0)
        img = Image.new("RGB", (10, 10), color)
        buf = _io.BytesIO()
        img.save(buf, "PNG")
        dest = Path(base_path).with_suffix(".png")
        dest.write_bytes(buf.getvalue())
        return dest

    monkeypatch.setattr(app_module.cover_search, "download_image_with_detected_ext", fake_download)

    game = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()

    res1 = client.post(f"/api/games/{game['id']}/cover-from-url", json={"url": "http://fake/first.png"})
    assert res1.status_code == 200
    cover_1 = res1.get_json()["cover_path"]

    res2 = client.post(f"/api/games/{game['id']}/cover-from-url", json={"url": "http://fake/second.png"})
    assert res2.status_code == 200
    cover_2 = res2.get_json()["cover_path"]

    assert cover_1 != cover_2  # cache-busting param changed
    updated = client.get(f"/api/games/{game['id']}").get_json()
    assert updated["cover_path"] == cover_2


def test_cover_from_url_returns_clear_error_on_download_failure(client, monkeypatch):
    """The frontend previously did nothing at all when this failed (no
    toast, no feedback) — the backend contract this relies on is that a
    failure always returns a real 'error' field, which it does."""
    import app as app_module

    monkeypatch.setattr(app_module.cover_search, "download_image_with_detected_ext", lambda url, base: None)

    game = client.post("/api/games", json={"title": "Celeste", "status": "backlog"}).get_json()
    res = client.post(f"/api/games/{game['id']}/cover-from-url", json={"url": "http://fake/broken.png"})
    assert res.status_code == 502
    assert res.get_json().get("error")


# ------------------------------------------------------------- Cover proxy (for the cover editor)

def test_cover_proxy_streams_valid_image_same_origin(client, monkeypatch):
    import app as app_module
    from PIL import Image
    import io as _io

    img = Image.new("RGB", (10, 10), (255, 0, 0))
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    png_bytes = buf.getvalue()

    class FakeResp:
        status_code = 200
        content = png_bytes
        headers = {"content-type": "image/png"}

    monkeypatch.setattr(app_module.requests, "get", lambda *a, **k: FakeResp())
    res = client.get("/api/cover-proxy?url=http://fake/cover.png")
    assert res.status_code == 200
    assert res.mimetype == "image/png"
    assert res.data == png_bytes


def test_cover_proxy_rejects_non_image_content(client, monkeypatch):
    import app as app_module

    class FakeResp:
        status_code = 200
        content = b"<html>not an image</html>"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(app_module.requests, "get", lambda *a, **k: FakeResp())
    res = client.get("/api/cover-proxy?url=http://fake/notreally.png")
    assert res.status_code == 502


def test_cover_proxy_requires_url_param(client):
    res = client.get("/api/cover-proxy")
    assert res.status_code == 400


def test_cover_proxy_handles_network_failure(client, monkeypatch):
    import app as app_module
    import requests as req_module

    def boom(*a, **k):
        raise req_module.RequestException("down")
    monkeypatch.setattr(app_module.requests, "get", boom)
    res = client.get("/api/cover-proxy?url=http://fake/cover.png")
    assert res.status_code == 502


# ------------------------------------------------------------- Deleting a game cleans up stale suggestions

def test_deleting_suggested_game_clears_dangling_reference(client):
    """A pending orphan-review suggestion pointing at a game that gets
    deleted must not keep dangling — confirming it later would otherwise
    silently do nothing while still marking the review as resolved."""
    game = client.post("/api/games", json={"title": "Suggested Game", "status": "completed"}).get_json()
    import app as app_module
    conn = app_module.get_conn()
    conn.execute(
        "INSERT INTO orphan_reviews (original_title, review, suggested_game_id, match_type) VALUES (?, ?, ?, ?)",
        ("X", "Y", game["id"], "fuzzy"),
    )
    conn.commit()
    conn.close()

    client.delete(f"/api/games/{game['id']}")

    orphans = client.get("/api/orphan-reviews").get_json()
    assert len(orphans) == 1
    assert orphans[0]["suggested_game_id"] is None
    assert orphans[0]["match_type"] is None


def test_deleting_suggested_game_promotes_an_alternative(client):
    """If an ambiguous suggestion's *primary* pick gets deleted but an
    alternative still exists, that alternative should be promoted rather
    than the whole suggestion being dropped."""
    primary = client.post("/api/games", json={"title": "Primary Pick", "status": "completed"}).get_json()
    alt = client.post("/api/games", json={"title": "Alt Pick", "status": "completed"}).get_json()
    import app as app_module
    import json as json_module
    conn = app_module.get_conn()
    conn.execute(
        "INSERT INTO orphan_reviews (original_title, review, suggested_game_id, match_type, alternative_game_ids) "
        "VALUES (?, ?, ?, ?, ?)",
        ("X", "Y", primary["id"], "ambiguous", json_module.dumps([alt["id"]])),
    )
    conn.commit()
    conn.close()

    client.delete(f"/api/games/{primary['id']}")

    orphans = client.get("/api/orphan-reviews").get_json()
    assert orphans[0]["suggested_game_id"] == alt["id"]


def test_link_orphan_review_rejects_nonexistent_target_game(client):
    """Linking to a game id that doesn't exist must fail loudly, not
    silently no-op while still marking the review as resolved."""
    client.post("/api/games", json={"title": "Real Game", "status": "completed"})
    import app as app_module
    conn = app_module.get_conn()
    conn.execute("INSERT INTO orphan_reviews (original_title, review) VALUES (?, ?)", ("X", "Y"))
    conn.commit()
    orphan_id = conn.execute("SELECT id FROM orphan_reviews").fetchone()["id"]
    conn.close()

    res = client.post(f"/api/orphan-reviews/{orphan_id}/link", json={"game_id": 99999})
    assert res.status_code == 404

    # The orphan review must still be pending, not falsely marked resolved.
    orphans = client.get("/api/orphan-reviews").get_json()
    assert len(orphans) == 1


