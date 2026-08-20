import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def temp_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKLOG_DATA_DIR", str(tmp_path))
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]
    from backend import db as db_module
    db_module.init_db()
    yield tmp_path


@pytest.fixture()
def temp_backup_dir(monkeypatch, tmp_path):
    """Isole aussi le dossier backup_backlog (sinon les tests écriraient dans
    le vrai dossier du projet)."""
    backup_dir = tmp_path / "backup_backlog"
    monkeypatch.setenv("BACKLOG_BACKUP_DIR", str(backup_dir))
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]
    yield backup_dir


def test_backup_creates_xlsx_and_csv(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    result = backup_mgr.create_backup(reason="save")
    assert result["xlsx"].endswith(".xlsx")
    assert result["csv"].endswith(".zip")
    backups = backup_mgr.list_backups()
    names = [b["name"] for b in backups]
    assert result["xlsx"] in names
    assert result["csv"] in names


def test_backup_filename_includes_player_name(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    from backend.db import save_config

    save_config({"configured": True, "player_name": "Alex Dupont!"})
    result = backup_mgr.create_backup()
    # le nom est assaini (espaces/ponctuation remplacés) mais reconnaissable
    assert "Alex_Dupont" in result["xlsx"]


def test_backup_rotation_keeps_only_3_versions_per_format(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    for _ in range(5):
        backup_mgr.create_backup()
        time.sleep(0.02)
    backups = backup_mgr.list_backups()
    xlsx_backups = [b for b in backups if b["name"].endswith(".xlsx")]
    csv_backups = [b for b in backups if b["name"].endswith(".zip")]
    assert len(xlsx_backups) == 3
    assert len(csv_backups) == 3


def test_restore_backup_from_xlsx_roundtrip(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status, rating) VALUES ('Jeu A', 'completed', 5)")
    conn.commit()
    conn.close()

    result = backup_mgr.create_backup()

    conn = get_conn()
    conn.execute("DELETE FROM games")
    conn.commit()
    conn.close()

    ok = backup_mgr.restore_backup(result["xlsx"])
    assert ok is True

    conn = get_conn()
    rows = conn.execute("SELECT * FROM games").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["title"] == "Jeu A"
    assert rows[0]["rating"] == 5


def test_restore_backup_from_csv_zip_roundtrip(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Jeu CSV', 'backlog')")
    conn.commit()
    conn.close()

    result = backup_mgr.create_backup()

    conn = get_conn()
    conn.execute("DELETE FROM games")
    conn.commit()
    conn.close()

    ok = backup_mgr.restore_backup(result["csv"])
    assert ok is True
    conn = get_conn()
    rows = conn.execute("SELECT * FROM games").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["title"] == "Jeu CSV"


def test_restore_backup_rejects_path_traversal(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    assert backup_mgr.restore_backup("../../etc/passwd") is False
    assert backup_mgr.restore_backup("..\\..\\windows") is False


def test_restore_backup_rejects_unknown_file(temp_data_dir, temp_backup_dir):
    from backend import backup as backup_mgr
    assert backup_mgr.restore_backup("does_not_exist.xlsx") is False


def test_restore_backup_rejects_zip_slip(temp_data_dir, temp_backup_dir):
    """A backup .zip is normally one this app produced itself, but
    restore_backup will happily open anything named right sitting in
    backup_backlog/ — so a zip whose internal entries try to escape the
    extraction directory (e.g. '../../../evil') must be rejected outright
    rather than partially extracted."""
    import zipfile
    from backend import backup as backup_mgr

    temp_backup_dir.mkdir(parents=True, exist_ok=True)
    evil_zip = temp_backup_dir / "evil.zip"
    canary = temp_data_dir.parent / "zip_slip_canary.txt"
    canary.unlink(missing_ok=True)

    # Path relative to wherever extractall's target dir ends up being —
    # several parent segments to comfortably escape a tempdir under /tmp.
    traversal_name = "../" * 6 + "zip_slip_canary.txt"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr(traversal_name, "pwned")
        zf.writestr("My_Backlog_-_Backlog.csv", "Jeu,Status\n")

    assert backup_mgr.restore_backup("evil.zip") is False
    assert not canary.exists()


def test_cover_search_candidates_parses_response(monkeypatch):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"items": [{"id": 1091500, "name": "Cyberpunk 2077"}]}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    results = cover_search.search_cover_candidates("Cyberpunk 2077")
    assert len(results) == 1
    assert results[0]["appid"] == 1091500
    assert "1091500" in results[0]["cover_url"]


def test_cover_search_handles_network_failure_gracefully(monkeypatch):
    from backend import covers as cover_search
    import requests

    def boom(*a, **k):
        raise requests.RequestException("network down")

    monkeypatch.setattr(cover_search.requests, "get", boom)
    results = cover_search.search_cover_candidates("Anything")
    assert results == []


def test_cover_search_empty_title_returns_empty(temp_data_dir):
    from backend import covers as cover_search
    assert cover_search.search_cover_candidates("") == []


def test_rawg_results_have_no_duplicate_fallback_url(monkeypatch, temp_data_dir):
    """Bug corrigé : quand fallback_url == cover_url, le navigateur retente la
    même URL déjà en échec en boucle ('clignotement'). RAWG/Wikipedia n'ont
    pas de 2e URL distincte, donc fallback_url doit être None, pas dupliqué."""
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"name": "Zelda", "background_image": "http://fake/img.jpg"}]}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    results = cover_search._search_rawg("Zelda", "fake-key")
    assert len(results) == 1
    assert results[0]["cover_url"] == "http://fake/img.jpg"
    assert results[0]["fallback_url"] is None


def test_search_cover_candidates_stops_early_once_enough_results(monkeypatch, temp_data_dir):
    """Optimisation : dès qu'on a assez de candidats, on n'interroge pas les
    variantes de requête restantes (moins d'appels réseau inutiles)."""
    from backend import covers as cover_search

    call_count = {"n": 0}

    def fake_steam(query):
        call_count["n"] += 1
        return [{"name": f"Résultat {i}", "source": "steam", "appid": i,
                  "cover_url": f"http://fake/{i}.jpg", "fallback_url": f"http://fake/{i}-hd.jpg"}
                for i in range(5)]

    # Titre générant plusieurs variantes de requête (parenthèses + sous-titre)
    monkeypatch.setattr(cover_search, "_search_steam", fake_steam)
    results = cover_search.search_cover_candidates("Un Jeu (Édition Spéciale) - Sous-titre", max_results=3)
    assert len(results) == 3
    assert call_count["n"] == 1  # une seule variante interrogée, pas les 3


def test_bulk_fill_covers_updates_all_missing_games(monkeypatch, temp_data_dir):
    """Vérifie que le remplissage en masse traite bien tous les jeux sans jaquette,
    met à jour la base, et laisse le statut cohérent une fois terminé."""
    from backend import covers as cover_search
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Celeste', 'completed')")
    conn.execute("INSERT INTO games (title, status) VALUES ('Outer Wilds', 'backlog')")
    conn.commit()
    conn.close()

    def fake_search(title, max_results=1, rawg_api_key=None, giantbomb_api_key=None,
                      steamgriddb_api_key=None, thegamesdb_api_key=None):
        return [{"name": title, "appid": 42, "cover_url": "http://fake/cover.jpg", "fallback_url": "http://fake/hdr.jpg"}]

    def fake_download(url, base_path):
        dest = Path(base_path).with_suffix(".jpg")
        dest.write_bytes(b"x" * 1000)
        return dest

    monkeypatch.setattr(cover_search, "search_cover_candidates", fake_search)
    monkeypatch.setattr(cover_search, "download_image_with_detected_ext", fake_download)
    monkeypatch.setattr(cover_search, "BULK_FILL_DELAY_SECONDS", 0)

    started = cover_search.start_bulk_fill()
    assert started is True

    # attend la fin du thread d'arrière-plan
    for _ in range(50):
        if not cover_search.get_bulk_status()["running"]:
            break
        time.sleep(0.05)

    status = cover_search.get_bulk_status()
    assert status["running"] is False
    assert status["total"] == 2
    assert status["found"] == 2

    conn = get_conn()
    rows = conn.execute("SELECT title, cover_path FROM games").fetchall()
    conn.close()
    assert all(r["cover_path"] for r in rows)


def test_bulk_fill_skips_game_when_placeholder_generation_also_fails(monkeypatch, temp_data_dir):
    """Now that a placeholder is the reliable fallback, a game only ends up
    'skipped' if even that fails (e.g. disk / Pillow error)."""
    from backend import covers as cover_search
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Jeu introuvable', 'backlog')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(cover_search, "search_cover_candidates", lambda title, max_results=1, rawg_api_key=None, giantbomb_api_key=None, steamgriddb_api_key=None, thegamesdb_api_key=None: [])
    monkeypatch.setattr(cover_search, "generate_placeholder_cover", lambda title, dest: False)
    monkeypatch.setattr(cover_search, "BULK_FILL_DELAY_SECONDS", 0)

    cover_search.start_bulk_fill()
    for _ in range(50):
        if not cover_search.get_bulk_status()["running"]:
            break
        time.sleep(0.05)

    status = cover_search.get_bulk_status()
    assert status["found"] == 0
    assert status["skipped"] == 1


def test_bulk_fill_survives_unexpected_exception_on_one_game(monkeypatch, temp_data_dir):
    """Si le traitement d'un jeu lève une exception inattendue (pas juste une
    absence de résultat réseau), le job ne doit jamais rester bloqué
    indéfiniment en 'running' — il doit continuer avec les jeux suivants."""
    from backend import covers as cover_search
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Jeu A', 'backlog')")
    conn.execute("INSERT INTO games (title, status) VALUES ('Jeu B', 'backlog')")
    conn.commit()
    conn.close()

    def boom(title, max_results=1, rawg_api_key=None, giantbomb_api_key=None,
              steamgriddb_api_key=None, thegamesdb_api_key=None):
        raise RuntimeError("erreur inattendue")

    monkeypatch.setattr(cover_search, "search_cover_candidates", boom)
    monkeypatch.setattr(cover_search, "BULK_FILL_DELAY_SECONDS", 0)

    started = cover_search.start_bulk_fill()
    assert started is True
    for _ in range(50):
        if not cover_search.get_bulk_status()["running"]:
            break
        time.sleep(0.05)

    status = cover_search.get_bulk_status()
    assert status["running"] is False
    assert status["done"] == 2
    assert status["skipped"] == 2


def test_giantbomb_search_without_key_returns_empty(temp_data_dir):
    from backend import covers as cover_search
    assert cover_search._search_giantbomb("Zelda", None) == []


def test_giantbomb_search_parses_results(monkeypatch, temp_data_dir):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"error": "OK", "results": [
                {"name": "Super Mario Odyssey",
                 "image": {"super_url": "http://fake/super.jpg", "medium_url": "http://fake/medium.jpg"}},
            ]}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    results = cover_search._search_giantbomb("Super Mario Odyssey", "fake-key")
    assert len(results) == 1
    assert results[0]["source"] == "giantbomb"
    assert results[0]["cover_url"] == "http://fake/super.jpg"
    assert results[0]["fallback_url"] == "http://fake/medium.jpg"


def test_giantbomb_search_handles_network_failure_gracefully(monkeypatch, temp_data_dir):
    from backend import covers as cover_search
    import requests as req_module

    def boom(*a, **k):
        raise req_module.RequestException("down")
    monkeypatch.setattr(cover_search.requests, "get", boom)
    assert cover_search._search_giantbomb("Anything", "fake-key") == []


def test_giantbomb_search_handles_api_error_status(monkeypatch, temp_data_dir):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"error": "Invalid API Key", "results": []}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    assert cover_search._search_giantbomb("Zelda", "bad-key") == []


def test_steamgriddb_search_without_key_returns_empty(temp_data_dir):
    from backend import covers as cover_search
    assert cover_search._search_steamgriddb("Zelda", None) == []


def test_steamgriddb_search_parses_grids(monkeypatch, temp_data_dir):
    """Two-step flow: search/autocomplete returns game ids, then /grids/game
    returns the portrait grids for each. Both must use the Bearer key."""
    from backend import covers as cover_search

    seen_headers = {}

    class FakeResp:
        status_code = 200
        def __init__(self, payload):
            self._payload = payload
        def raise_for_status(self): pass
        def json(self):
            return self._payload

    def fake_get(url, params=None, headers=None, timeout=None):
        seen_headers.setdefault("auth", []).append(headers.get("Authorization"))
        if "/search/autocomplete/" in url:
            return FakeResp({"success": True, "data": [{"id": 5, "name": "Celeste"}]})
        if "/grids/game/" in url:
            return FakeResp({"success": True, "data": [
                {"url": "http://fake/grid.png", "thumb": "http://fake/thumb.png"},
            ]})
        return FakeResp({"success": False})

    monkeypatch.setattr(cover_search.requests, "get", fake_get)
    results = cover_search._search_steamgriddb("Celeste", "sgdb-key")
    assert len(results) == 1
    assert results[0]["source"] == "steamgriddb"
    assert results[0]["cover_url"] == "http://fake/grid.png"
    assert results[0]["fallback_url"] == "http://fake/thumb.png"
    assert all(h == "Bearer sgdb-key" for h in seen_headers["auth"])


def test_steamgriddb_search_handles_network_failure_gracefully(monkeypatch, temp_data_dir):
    from backend import covers as cover_search
    import requests as req_module

    def boom(*a, **k):
        raise req_module.RequestException("down")
    monkeypatch.setattr(cover_search.requests, "get", boom)
    assert cover_search._search_steamgriddb("Anything", "fake-key") == []


def test_steamgriddb_search_encodes_title_in_url_path(monkeypatch, temp_data_dir):
    """The search term sits in the URL *path* for this source (unlike every
    other source, which passes it via `params=`), so it must be percent-
    encoded by hand. A title with '/', '&', '?', or '#' would otherwise
    split the path, get treated as a query string, or get truncated."""
    from backend import covers as cover_search

    seen_urls = []

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"success": True, "data": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen_urls.append(url)
        return FakeResp()

    monkeypatch.setattr(cover_search.requests, "get", fake_get)
    cover_search._search_steamgriddb("Bloons TD 6 & Friends / Deluxe?", "sgdb-key")
    assert len(seen_urls) == 1
    assert "/" not in seen_urls[0].split("/search/autocomplete/", 1)[1]
    assert "&" not in seen_urls[0].split("/search/autocomplete/", 1)[1]
    assert seen_urls[0].split("/search/autocomplete/", 1)[1].startswith("Bloons%20TD%206")


def test_steamgriddb_search_skips_when_autocomplete_unsuccessful(monkeypatch, temp_data_dir):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"success": False, "errors": ["bad key"]}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    assert cover_search._search_steamgriddb("Anything", "bad-key") == []


def test_thegamesdb_search_without_key_returns_empty(temp_data_dir):
    from backend import covers as cover_search
    assert cover_search._search_thegamesdb("Zelda", None) == []


def test_thegamesdb_search_parses_front_boxart(monkeypatch, temp_data_dir):
    """Two-step flow: ByGameName returns game ids, then Games/Images returns
    boxart keyed by game id. Only front boxart is kept, joined with the
    original base_url."""
    from backend import covers as cover_search

    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"code": 200, "data": {"games": [{"id": 1, "game_title": "Celeste"}]}}
            return {"code": 200, "data": {
                "base_url": {"original": "https://cdn.thegamesdb.net/images/original/"},
                "boxart": {"1": [
                    {"type": "boxart", "side": "front", "filename": "boxart/front/1-1.jpg"},
                    {"type": "boxart", "side": "back", "filename": "boxart/back/1-1.jpg"},
                ]},
            }}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    results = cover_search._search_thegamesdb("Celeste", "tgdb-key")
    assert len(results) == 1
    assert results[0]["source"] == "thegamesdb"
    assert results[0]["cover_url"] == "https://cdn.thegamesdb.net/images/original/boxart/front/1-1.jpg"
    assert results[0]["fallback_url"] is None


def test_thegamesdb_search_handles_network_failure_gracefully(monkeypatch, temp_data_dir):
    from backend import covers as cover_search
    import requests as req_module

    def boom(*a, **k):
        raise req_module.RequestException("down")
    monkeypatch.setattr(cover_search.requests, "get", boom)
    assert cover_search._search_thegamesdb("Anything", "fake-key") == []


def test_thegamesdb_search_handles_api_error_code(monkeypatch, temp_data_dir):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"code": 401, "status": "Invalid API Key"}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    assert cover_search._search_thegamesdb("Anything", "bad-key") == []


def test_cover_search_merges_all_configured_providers(monkeypatch, temp_data_dir):
    """A keyed source with no key is silently skipped, and every configured
    key adds its candidates to the merged, re-ranked result set."""
    from backend import covers as cover_search

    monkeypatch.setattr(cover_search, "_search_steam", lambda q: [])
    monkeypatch.setattr(cover_search, "_search_steamgriddb",
                        lambda q, k: [{"name": q, "source": "steamgriddb",
                                      "cover_url": "http://fake/sgdb.png", "fallback_url": None}])
    monkeypatch.setattr(cover_search, "_search_rawg",
                        lambda q, k: [{"name": q, "source": "rawg",
                                      "cover_url": "http://fake/rawg.jpg", "fallback_url": None}])
    monkeypatch.setattr(cover_search, "_search_giantbomb",
                        lambda q, k: [{"name": q, "source": "giantbomb",
                                      "cover_url": "http://fake/gb.jpg", "fallback_url": None}])
    monkeypatch.setattr(cover_search, "_search_thegamesdb",
                        lambda q, k: [{"name": q, "source": "thegamesdb",
                                      "cover_url": "http://fake/tgdb.jpg", "fallback_url": None}])
    results = cover_search.search_cover_candidates(
        "Celeste", steamgriddb_api_key="k1", rawg_api_key="k2",
        giantbomb_api_key="k3", thegamesdb_api_key="k4")
    sources = {r["source"] for r in results}
    assert sources == {"steamgriddb", "rawg", "giantbomb", "thegamesdb"}


def test_cover_search_does_not_let_one_source_crowd_out_the_others(monkeypatch, temp_data_dir):
    """Regression test: Steam needs no key and can return many close string
    matches on its own. A naive 'merge everything, sort by similarity,
    truncate to max_results' would let Steam alone fill every slot even
    when other configured sources found perfectly good (if slightly less
    textually similar) candidates — silently hiding every other source
    from the results the user actually sees."""
    from backend import covers as cover_search

    # Steam "wins" on pure string similarity for every one of its 6 hits...
    monkeypatch.setattr(cover_search, "_search_steam", lambda q: [
        {"name": "Celeste", "source": "steam", "appid": i,
         "cover_url": f"http://fake/steam{i}.jpg", "fallback_url": None}
        for i in range(6)
    ])
    # ...while SteamGridDB only has one, slightly-less-similar-named hit.
    monkeypatch.setattr(cover_search, "_search_steamgriddb", lambda q, k: [
        {"name": "Celeste (Special Edition)", "source": "steamgriddb",
         "cover_url": "http://fake/sgdb.png", "fallback_url": None}
    ])
    results = cover_search.search_cover_candidates("Celeste", max_results=4, steamgriddb_api_key="k1")
    sources = {r["source"] for r in results}
    assert "steamgriddb" in sources, "SteamGridDB's result got crowded out by Steam's volume"
    assert "steam" in sources


def test_wikipedia_search_uses_combined_query_and_parses_pageimages(monkeypatch, temp_data_dir):
    """The Wikipedia fallback should pull image + search in a single request
    (generator=search + pageimages) rather than one search call followed by
    N per-article follow-ups."""
    from backend import covers as cover_search

    call_count = {"n": 0}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            call_count["n"] += 1
            return {"query": {"pages": {
                "123": {"title": "Celeste (video game)",
                        "original": {"source": "http://fake/celeste.jpg"}},
                "456": {"title": "Celeste (disambiguation)"},  # no image: skipped
            }}}

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    results = cover_search._search_wikipedia("Celeste")
    assert call_count["n"] == 1  # single combined request
    assert len(results) == 1
    assert results[0]["cover_url"] == "http://fake/celeste.jpg"
    assert results[0]["source"] == "wikipedia"


def test_wikipedia_search_handles_network_failure_gracefully(monkeypatch, temp_data_dir):
    from backend import covers as cover_search
    import requests as req_module

    def boom(*a, **k):
        raise req_module.RequestException("down")
    monkeypatch.setattr(cover_search.requests, "get", boom)
    assert cover_search._search_wikipedia("Anything") == []


def test_generate_placeholder_cover_produces_valid_image(temp_data_dir, tmp_path):
    from backend import covers as cover_search

    dest = tmp_path / "placeholder.png"
    ok = cover_search.generate_placeholder_cover("Some Obscure Game Nobody Has Heard Of", dest)
    assert ok is True
    assert dest.exists()
    assert cover_search.is_valid_image(dest)


def test_generate_placeholder_cover_is_deterministic(temp_data_dir, tmp_path):
    """Same title -> same color, so re-generating (e.g. re-running bulk fill)
    doesn't produce a randomly different placeholder each time."""
    from backend import covers as cover_search
    from PIL import Image

    dest1, dest2 = tmp_path / "a.png", tmp_path / "b.png"
    cover_search.generate_placeholder_cover("Same Title", dest1)
    cover_search.generate_placeholder_cover("Same Title", dest2)
    px1 = Image.open(dest1).getpixel((0, 0))
    px2 = Image.open(dest2).getpixel((0, 0))
    assert px1 == px2


def test_bulk_fill_falls_back_to_placeholder_when_nothing_found(monkeypatch, temp_data_dir):
    """When every real source comes up empty, the bulk fill must still leave
    the game with a cover (the generated placeholder) rather than skipping
    it — this is the 'reliable fallback' requirement."""
    from backend import covers as cover_search
    from backend.db import get_conn

    conn = get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Totally Obscure Game', 'backlog')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(cover_search, "search_cover_candidates", lambda *a, **k: [])
    monkeypatch.setattr(cover_search, "BULK_FILL_DELAY_SECONDS", 0)

    cover_search.start_bulk_fill()
    for _ in range(50):
        if not cover_search.get_bulk_status()["running"]:
            break
        time.sleep(0.05)

    status = cover_search.get_bulk_status()
    assert status["found"] == 1
    assert status["skipped"] == 0

    conn = get_conn()
    row = conn.execute("SELECT cover_path FROM games").fetchone()
    conn.close()
    assert row["cover_path"]


def test_bulk_fill_refuses_concurrent_runs(monkeypatch, temp_data_dir):
    from backend import covers as cover_search

    def slow_search(title, max_results=1):
        time.sleep(0.3)
        return []

    conn_mod = __import__("backend.db", fromlist=["get_conn"])
    conn = conn_mod.get_conn()
    conn.execute("INSERT INTO games (title, status) VALUES ('Jeu lent', 'backlog')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(cover_search, "search_cover_candidates", slow_search)
    first = cover_search.start_bulk_fill()
    second = cover_search.start_bulk_fill()
    assert first is True
    assert second is False

    for _ in range(50):
        if not cover_search.get_bulk_status()["running"]:
            break
        time.sleep(0.05)
