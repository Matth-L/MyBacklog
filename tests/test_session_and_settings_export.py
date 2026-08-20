import sys
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


def test_settings_included_in_xlsx_export(temp_data_dir):
    from backend.db import save_config
    from backend import exporter
    import pandas as pd
    import io

    save_config({"configured": True, "player_name": "Alex", "rawg_api_key": "abc123"})
    xlsx_bytes = exporter.export_xlsx()
    xl = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    assert "Settings" in xl.sheet_names
    df = pd.read_excel(xl, "Settings")
    row = df[df["Clé"] == "player_name"].iloc[0]
    assert row["Valeur"] == "Alex"


def test_settings_included_in_csv_zip_export(temp_data_dir):
    from backend.db import save_config
    from backend import exporter
    import zipfile
    import io
    import json

    save_config({"configured": True, "player_name": "Sam"})
    zip_bytes = exporter.export_csv_zip()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert "settings.json" in zf.namelist()
        settings = json.loads(zf.read("settings.json"))
    assert settings["player_name"] == "Sam"


def test_import_new_session_clears_previous_data_and_restores_settings(temp_data_dir, tmp_path):
    from backend.db import get_conn, save_config, load_config
    from backend import exporter, session as session_mgr

    # Seed an initial session with one game and a distinct player name.
    save_config({"configured": True, "player_name": "OldPlayer"})
    conn = get_conn()
    conn.execute("INSERT INTO games (title, status, rating) VALUES ('Old Game', 'completed', 8)")
    conn.commit()
    conn.close()

    # Export it as the "new" file to import (with a different player name set
    # right before export, to prove settings travel with the file).
    save_config({"configured": True, "player_name": "NewPlayer"})
    conn = get_conn()
    conn.execute("INSERT INTO games (title, status, rating) VALUES ('New Game', 'completed', 9)")
    conn.commit()
    conn.close()
    xlsx_path = tmp_path / "new_session.xlsx"
    xlsx_path.write_bytes(exporter.export_xlsx())

    # Reset to a third state, simulating "current session before import".
    save_config({"configured": True, "player_name": "CurrentPlayer"})
    conn = get_conn()
    conn.execute("DELETE FROM games")
    conn.execute("INSERT INTO games (title, status, rating) VALUES ('Current Game', 'completed', 1)")
    conn.commit()
    conn.close()

    summary = session_mgr.import_new_session(str(xlsx_path))
    assert summary["completed_imported"] == 2  # Old Game + New Game from the exported file

    conn = get_conn()
    titles = {r["title"] for r in conn.execute("SELECT title FROM games").fetchall()}
    conn.close()
    assert "Current Game" not in titles  # previous session was cleared
    assert "Old Game" in titles and "New Game" in titles

    assert load_config()["player_name"] == "NewPlayer"  # settings restored from the file


def test_import_new_session_rejects_missing_file(temp_data_dir, tmp_path):
    from backend import session as session_mgr

    with pytest.raises(session_mgr.SessionImportError):
        session_mgr.import_new_session(str(tmp_path / "does_not_exist.xlsx"))


def test_import_new_session_rejects_unsupported_extension(temp_data_dir, tmp_path):
    from backend import session as session_mgr

    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    with pytest.raises(session_mgr.SessionImportError):
        session_mgr.import_new_session(str(bad))


def test_import_new_session_rejects_zip_slip(temp_data_dir, tmp_path):
    """A session .zip whose entries try to escape the extraction directory
    must be rejected with SessionImportError('unsafe_zip'), not partially
    extracted onto the filesystem."""
    import zipfile
    from backend import session as session_mgr

    evil_zip = tmp_path / "evil_session.zip"
    canary = tmp_path.parent / "session_zip_slip_canary.txt"
    canary.unlink(missing_ok=True)

    traversal_name = "../" * 6 + "session_zip_slip_canary.txt"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr(traversal_name, "pwned")

    with pytest.raises(session_mgr.SessionImportError) as excinfo:
        session_mgr.import_new_session(str(evil_zip))
    assert excinfo.value.code == "unsafe_zip"
    assert not canary.exists()
