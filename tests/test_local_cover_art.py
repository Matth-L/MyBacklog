import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def temp_cover_art_dir(monkeypatch, tmp_path):
    cover_dir = tmp_path / "cover_art"
    cover_dir.mkdir()
    monkeypatch.setenv("BACKLOG_COVER_ART_DIR", str(cover_dir))
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]
    yield cover_dir


def _make_png_bytes():
    import random
    from PIL import Image
    img = Image.new("RGB", (60, 60))
    img.putdata([
        (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        for _ in range(60 * 60)
    ])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_normalize_filename_ignores_case_spaces_underscores(temp_cover_art_dir):
    from backend import covers as cover_search
    assert cover_search._normalize_filename("Persona 5 Royal") == "persona5royal"
    assert cover_search._normalize_filename("persona_5_royal") == "persona5royal"
    assert cover_search._normalize_filename("PERSONA-5-ROYAL") == "persona5royal"


@pytest.mark.parametrize("filename", [
    "persona_5_royal.jpg", "Persona5Royal.png", "PERSONA 5 ROYAL.webp", "persona-5-royal.jpeg",
])
def test_find_local_cover_matches_various_filename_styles(temp_cover_art_dir, filename):
    from backend import covers as cover_search
    (temp_cover_art_dir / filename).write_bytes(_make_png_bytes())
    found = cover_search.find_local_cover("Persona 5 Royal")
    assert found is not None
    assert found.name == filename


def test_find_local_cover_returns_none_when_no_match(temp_cover_art_dir):
    from backend import covers as cover_search
    (temp_cover_art_dir / "some_other_game.jpg").write_bytes(_make_png_bytes())
    assert cover_search.find_local_cover("Persona 5 Royal") is None


def test_build_local_cover_index_and_lookup_matches_direct_scan(temp_cover_art_dir):
    """L'index pré-construit (utilisé pour le remplissage en masse, afin
    d'éviter de rescanner le dossier à chaque jeu) doit donner exactement le
    même résultat que le scan direct au cas par cas."""
    from backend import covers as cover_search
    (temp_cover_art_dir / "celeste.jpg").write_bytes(_make_png_bytes())
    (temp_cover_art_dir / "Hollow_Knight.png").write_bytes(_make_png_bytes())

    index = cover_search.build_local_cover_index()
    assert cover_search.find_local_cover("Celeste", index=index).name == "celeste.jpg"
    assert cover_search.find_local_cover("Hollow Knight", index=index).name == "Hollow_Knight.png"
    assert cover_search.find_local_cover("Jeu inexistant", index=index) is None
    # cohérent avec un scan direct (sans index)
    assert cover_search.find_local_cover("Celeste").name == "celeste.jpg"


def test_build_local_cover_index_empty_when_folder_missing(monkeypatch, tmp_path):
    from backend import covers as cover_search
    monkeypatch.setattr(cover_search, "COVER_ART_DIR", tmp_path / "does_not_exist")
    assert cover_search.build_local_cover_index() == {}


def test_find_local_cover_ignores_non_image_files(temp_cover_art_dir):
    from backend import covers as cover_search
    (temp_cover_art_dir / "persona5royal.txt").write_text("not an image")
    assert cover_search.find_local_cover("Persona 5 Royal") is None


def test_is_valid_image_accepts_real_image_bytes(temp_cover_art_dir):
    from backend import covers as cover_search
    assert cover_search.is_valid_image(_make_png_bytes()) is True


def test_is_valid_image_rejects_non_image_content(temp_cover_art_dir):
    from backend import covers as cover_search
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00this is not an image, it's an exe"
    assert cover_search.is_valid_image(fake_exe) is False


def test_is_valid_image_rejects_text_masquerading_as_image(temp_cover_art_dir):
    from backend import covers as cover_search
    assert cover_search.is_valid_image(b"<html>not an image</html>") is False


def test_safe_title_filename_sanitizes_and_stays_unique():
    from backend import covers as cover_search
    name = cover_search.safe_title_filename("Nier: Automata (A)", 42, ".jpg")
    assert name.endswith("_42.jpg")
    assert " " not in name
    assert ":" not in name
    assert "(" not in name


def test_search_with_local_prefers_reporting_both_when_available(monkeypatch, temp_cover_art_dir):
    from backend import covers as cover_search
    (temp_cover_art_dir / "celeste.jpg").write_bytes(_make_png_bytes())

    monkeypatch.setattr(
        cover_search, "search_cover_candidates",
        lambda title, max_results=8, rawg_api_key=None, giantbomb_api_key=None: [
            {"name": "Celeste", "cover_url": "http://fake/cover.jpg", "fallback_url": "http://fake/hdr.jpg"}
        ],
    )
    result = cover_search.search_with_local("Celeste")
    assert result["local_match"]["filename"] == "celeste.jpg"
    assert len(result["online"]) == 1


def test_search_with_local_handles_no_local_match(monkeypatch, temp_cover_art_dir):
    from backend import covers as cover_search
    monkeypatch.setattr(
        cover_search, "search_cover_candidates",
        lambda title, max_results=8, rawg_api_key=None, giantbomb_api_key=None: [],
    )
    result = cover_search.search_with_local("Un jeu quelconque")
    assert result["local_match"] is None
    assert result["online"] == []


def test_download_image_rejects_non_image_response(monkeypatch, tmp_path):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        headers = {"content-type": "application/octet-stream"}
        content = b"x" * 1000  # assez gros pour passer le contrôle de taille, mais pas une image

        def raise_for_status(self):
            pass

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    ok = cover_search.download_image("http://fake/evil.exe", tmp_path / "out.jpg")
    assert ok is False
    assert not (tmp_path / "out.jpg").exists()


def test_download_image_accepts_real_image(monkeypatch, tmp_path):
    from backend import covers as cover_search

    class FakeResp:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = _make_png_bytes()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(cover_search.requests, "get", lambda *a, **k: FakeResp())
    ok = cover_search.download_image("http://fake/cover.png", tmp_path / "out.png")
    assert ok is True
    assert (tmp_path / "out.png").exists()
