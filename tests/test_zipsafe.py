"""Unit tests for backend.zipsafe.safe_extractall — the shared zip-slip
guard used by both session import and backup restore."""
import zipfile

import pytest


def test_safe_extractall_extracts_normal_zip(tmp_path):
    from backend.zipsafe import safe_extractall

    src = tmp_path / "normal.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("a.txt", "hello")
        zf.writestr("sub/b.txt", "world")

    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        safe_extractall(zf, dest)

    assert (dest / "a.txt").read_text() == "hello"
    assert (dest / "sub" / "b.txt").read_text() == "world"


def test_safe_extractall_rejects_relative_traversal(tmp_path):
    from backend.zipsafe import safe_extractall, UnsafeZipError

    src = tmp_path / "evil.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("../../../etc/passwd", "pwned")

    dest = tmp_path / "out"
    dest.mkdir()
    canary = tmp_path.parent / "etc" / "passwd"

    with zipfile.ZipFile(src) as zf:
        with pytest.raises(UnsafeZipError):
            safe_extractall(zf, dest)

    assert not canary.exists()


def test_safe_extractall_rejects_absolute_path(tmp_path):
    from backend.zipsafe import safe_extractall, UnsafeZipError

    src = tmp_path / "evil_abs.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr(str(tmp_path / "outside.txt"), "pwned")

    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        with pytest.raises(UnsafeZipError):
            safe_extractall(zf, dest)


def test_safe_extractall_extracts_nothing_when_one_entry_is_unsafe(tmp_path):
    """Fails closed: if any single entry is unsafe, nothing from the zip
    should be extracted — not the safe entries followed by a failure
    partway through."""
    from backend.zipsafe import safe_extractall, UnsafeZipError

    src = tmp_path / "mixed.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("safe.txt", "fine")
        zf.writestr("../escape.txt", "pwned")

    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        with pytest.raises(UnsafeZipError):
            safe_extractall(zf, dest)

    assert not (dest / "safe.txt").exists()
