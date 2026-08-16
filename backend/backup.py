"""One-off backups, triggered only by an explicit user action (saving a new
game, editing a review, or importing a file) — no periodic background
autosave.

Each backup produces both an .xlsx file AND a .csv file (zip of the 3 csv),
timestamped and named after the player, in a 'backup_backlog' folder at the
project root. At most 3 versions of each format are kept."""
import os
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from . import exporter, applog
from .db import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path(os.environ.get("BACKLOG_BACKUP_DIR", PROJECT_ROOT / "backup_backlog"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

MAX_VERSIONS = 3


def _safe_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "").strip())
    return name or "user"


def _rotate(pattern: str):
    files = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[MAX_VERSIONS:]:
        old.unlink(missing_ok=True)


def create_backup(reason: str = "save") -> dict:
    """Creates a timestamped .xlsx and .csv snapshot. Always called
    explicitly (never by a background timer)."""
    cfg = load_config()
    username = _safe_name(cfg.get("player_name") or "user")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    xlsx_name = f"MyBacklog_{timestamp}_{username}.xlsx"
    (BACKUP_DIR / xlsx_name).write_bytes(exporter.export_xlsx())
    _rotate("*.xlsx")

    csv_name = f"MyBacklog_{timestamp}_{username}.zip"
    (BACKUP_DIR / csv_name).write_bytes(exporter.export_csv_zip())
    _rotate("*.zip")

    applog.info(f"Backup saved ({reason}): {xlsx_name}")
    return {"xlsx": xlsx_name, "csv": csv_name, "reason": reason}


def list_backups():
    files = sorted(BACKUP_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1),
         "date": datetime.fromtimestamp(p.stat().st_mtime).isoformat()}
        for p in files if p.is_file()
    ]


def restore_backup(name: str) -> bool:
    """Replaces the current data with the content of an .xlsx or .zip (csv)
    backup from the backup_backlog folder."""
    if ".." in name or "/" in name or "\\" in name:
        return False
    path = BACKUP_DIR / name
    if not path.exists():
        return False

    from .db import get_conn, save_config
    from .importer import import_all, extract_settings_from_xlsx

    conn = get_conn()
    conn.execute("DELETE FROM games")
    conn.execute("DELETE FROM orphan_reviews")
    conn.commit()
    conn.close()

    if name.endswith(".xlsx"):
        import_all(xlsx_path=str(path))
        settings = extract_settings_from_xlsx(str(path))
        if settings:
            cfg = load_config()
            cfg.update(settings)
            save_config(cfg)
    elif name.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(tmp)
            tmp_path = Path(tmp)
            import_all(
                backlog_csv=str(tmp_path / "My_Backlog_-_Backlog.csv"),
                avis_csv=str(tmp_path / "My_Backlog_-_Avis.csv"),
                complete_csv=str(tmp_path / "My_Backlog_-_Complete.csv"),
            )
            settings_json = tmp_path / "settings.json"
            if settings_json.exists():
                try:
                    import json
                    settings = json.loads(settings_json.read_text(encoding="utf-8"))
                    cfg = load_config()
                    cfg.update(settings)
                    save_config(cfg)
                except (OSError, ValueError):
                    pass
    else:
        return False
    applog.info(f"Backup restored: {name}")
    return True
