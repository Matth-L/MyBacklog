"""Import another Excel file / session at any time.

Unlike the first-run setup import, this always clears the current session
first (games + orphan reviews) before loading the new data, and can restore
the "Settings" sheet / settings.json bundled in the file if present, so a
full session (data + user settings) can be moved between machines.
"""
import json
import tempfile
import zipfile
from pathlib import Path

from . import applog
from .db import get_conn, load_config, save_config
from .importer import import_all, extract_settings_from_xlsx


class SessionImportError(Exception):
    pass


def clear_session():
    """Wipes current games/reviews. Never touches app settings (theme,
    language, API keys...) — only the backlog data itself."""
    conn = get_conn()
    conn.execute("DELETE FROM games")
    conn.execute("DELETE FROM orphan_reviews")
    conn.commit()
    conn.close()


def _apply_settings(settings: dict):
    if not settings:
        return
    cfg = load_config()
    cfg.update(settings)
    save_config(cfg)


def import_new_session(path: str) -> dict:
    """Clears the current session, then imports from a local path: a
    .xlsx file, or a My_Backlog csv-export .zip (both formats produced by
    this application's own export). Returns an import summary."""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        raise SessionImportError(f"File not found: {path}")

    suffix = p.suffix.lower()
    if suffix not in (".xlsx", ".zip"):
        raise SessionImportError("Only .xlsx or .zip (exported session) files are supported.")

    clear_session()

    if suffix == ".xlsx":
        summary = import_all(xlsx_path=str(p))
        settings = extract_settings_from_xlsx(str(p))
        _apply_settings(settings)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(p) as zf:
                zf.extractall(tmp)
            tmp_path = Path(tmp)
            backlog_csv = tmp_path / "My_Backlog_-_Backlog.csv"
            avis_csv = tmp_path / "My_Backlog_-_Avis.csv"
            complete_csv = tmp_path / "My_Backlog_-_Complete.csv"
            settings_json = tmp_path / "settings.json"
            missing = [f.name for f in (backlog_csv, avis_csv, complete_csv) if not f.exists()]
            if missing:
                raise SessionImportError(
                    "This zip doesn't look like a MyBacklog export "
                    f"(missing: {', '.join(missing)})."
                )
            summary = import_all(
                backlog_csv=str(backlog_csv), avis_csv=str(avis_csv), complete_csv=str(complete_csv),
            )
            if settings_json.exists():
                try:
                    _apply_settings(json.loads(settings_json.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    pass

    applog.info(f"Session imported from {p.name} "
                f"({summary['completed_imported']} completed, {summary['backlog_imported']} backlog).")
    return summary
