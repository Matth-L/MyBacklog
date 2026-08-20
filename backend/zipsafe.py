"""Safe zip extraction, shared by session import and backup restore.

`zipfile.ZipFile.extractall()` does not validate member paths. A crafted
zip can contain an entry like `../../../../home/user/.bashrc` or an
absolute path, which — extracted naively — writes outside the intended
temp directory (a "zip slip" vulnerability). Both call sites that extract
a zip in this app accept one supplied by the user (a file uploaded through
the browser, or a file dropped into backup_backlog/), so both route
through `safe_extractall()` instead of calling `extractall()` directly.
"""
import zipfile
from pathlib import Path


class UnsafeZipError(Exception):
    """Raised when a zip contains an entry that would extract outside the
    target directory."""


def _is_within_directory(directory: Path, target: Path) -> bool:
    try:
        target.relative_to(directory)
        return True
    except ValueError:
        return False


def safe_extractall(zf: zipfile.ZipFile, dest_dir) -> None:
    """Like `zf.extractall(dest_dir)`, but first verifies every member
    would land inside `dest_dir` once resolved, and raises UnsafeZipError
    (extracting nothing) if any entry tries to escape it — rather than
    extracting the safe entries and only failing partway through."""
    dest_dir = Path(dest_dir).resolve()
    for member in zf.infolist():
        target = (dest_dir / member.filename).resolve()
        if not _is_within_directory(dest_dir, target):
            raise UnsafeZipError(f"Unsafe path in zip entry: {member.filename!r}")
    zf.extractall(dest_dir)
