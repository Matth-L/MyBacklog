import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_fetch_estimated_hours_returns_none_for_empty_title():
    from backend import hltb
    assert hltb.fetch_estimated_hours("") is None
    assert hltb.fetch_estimated_hours(None) is None


def test_fetch_estimated_hours_rejects_unknown_mode():
    from backend import hltb
    with pytest.raises(hltb.HLTBError):
        hltb.fetch_estimated_hours("Celeste", mode="speedrun")


def test_fetch_estimated_hours_returns_none_on_no_results(monkeypatch):
    from backend import hltb

    class FakeHLTB:
        def search(self, title):
            return []

    monkeypatch.setattr(hltb, "HowLongToBeat", FakeHLTB)
    assert hltb.fetch_estimated_hours("Some Obscure Game") is None


def test_fetch_estimated_hours_picks_best_similarity_match(monkeypatch):
    from backend import hltb

    class FakeEntry:
        def __init__(self, name, similarity, main_story, main_extra, completionist):
            self.game_name = name
            self.similarity = similarity
            self.main_story = main_story
            self.main_extra = main_extra
            self.completionist = completionist

    class FakeHLTB:
        def search(self, title):
            return [
                FakeEntry("Celeste Classic", 0.4, 1.0, 1.0, 1.0),
                FakeEntry("Celeste", 0.95, 8.5, 12.0, 37.5),
            ]

    monkeypatch.setattr(hltb, "HowLongToBeat", FakeHLTB)
    assert hltb.fetch_estimated_hours("Celeste", mode="main") == 8.5
    assert hltb.fetch_estimated_hours("Celeste", mode="main_extra") == 12.0
    assert hltb.fetch_estimated_hours("Celeste", mode="completionist") == 37.5


def test_fetch_estimated_hours_returns_none_when_mode_has_no_data(monkeypatch):
    from backend import hltb

    class FakeEntry:
        similarity = 1.0
        game_name = "Multiplayer Only Game"
        main_story = None
        main_extra = None
        completionist = None

    class FakeHLTB:
        def search(self, title):
            return [FakeEntry()]

    monkeypatch.setattr(hltb, "HowLongToBeat", FakeHLTB)
    assert hltb.fetch_estimated_hours("Multiplayer Only Game", mode="main") is None


def test_fetch_estimated_hours_survives_network_failure(monkeypatch):
    from backend import hltb

    class FakeHLTB:
        def search(self, title):
            raise ConnectionError("network down")

    monkeypatch.setattr(hltb, "HowLongToBeat", FakeHLTB)
    assert hltb.fetch_estimated_hours("Anything") is None


# ------------------------------------------------------------- Endpoint-level behavior

@pytest.fixture()
def client(monkeypatch, tmp_path):
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


def test_fetch_hltb_endpoint_updates_hours_estimated(client, monkeypatch):
    import app as app_module

    res = client.post("/api/games", json={"title": "Hollow Knight"})
    game_id = res.get_json()["id"]

    monkeypatch.setattr(app_module.hltb, "fetch_estimated_hours", lambda title, mode: 27.5)
    res = client.post(f"/api/games/{game_id}/fetch-hltb", json={"mode": "main"})
    assert res.status_code == 200
    assert res.get_json()["hours_estimated"] == 27.5

    res = client.get(f"/api/games/{game_id}")
    assert res.get_json()["hours_estimated"] == 27.5


def test_fetch_hltb_endpoint_overwrites_even_if_already_set(client, monkeypatch):
    """The backend no longer blocks based on the last-saved DB value: the
    frontend is the one gating this (button only shown while the field is
    empty), since the DB value can be stale mid-edit (field cleared but not
    yet saved). An explicit fetch call always proceeds."""
    import app as app_module

    res = client.post("/api/games", json={"title": "Hades", "hours_estimated": 20})
    game_id = res.get_json()["id"]

    monkeypatch.setattr(app_module.hltb, "fetch_estimated_hours", lambda title, mode: 99)
    res = client.post(f"/api/games/{game_id}/fetch-hltb", json={"mode": "main"})
    assert res.status_code == 200
    assert res.get_json()["hours_estimated"] == 99

    res = client.get(f"/api/games/{game_id}")
    assert res.get_json()["hours_estimated"] == 99


def test_fetch_hltb_endpoint_returns_404_when_no_match(client, monkeypatch):
    import app as app_module

    res = client.post("/api/games", json={"title": "Totally Made Up Game Title Xyz"})
    game_id = res.get_json()["id"]

    monkeypatch.setattr(app_module.hltb, "fetch_estimated_hours", lambda title, mode: None)
    res = client.post(f"/api/games/{game_id}/fetch-hltb", json={"mode": "main"})
    assert res.status_code == 404
    assert res.get_json()["code"] == "no_match"


def test_fetch_hltb_endpoint_rejects_invalid_mode(client):
    res = client.post("/api/games", json={"title": "Some Game"})
    game_id = res.get_json()["id"]
    res = client.post(f"/api/games/{game_id}/fetch-hltb", json={"mode": "not-a-real-mode"})
    assert res.status_code == 400


def test_hltb_lookup_by_title_does_not_require_a_saved_game(client, monkeypatch):
    """Powers the estimate button in the "new game" modal, before the game
    has been saved (and so has no id yet) — a plain title lookup, no DB
    write."""
    import app as app_module

    monkeypatch.setattr(app_module.hltb, "fetch_estimated_hours", lambda title, mode: 12.5)
    res = client.post("/api/hltb/lookup", json={"title": "Celeste", "mode": "main"})
    assert res.status_code == 200
    assert res.get_json()["hours_estimated"] == 12.5


def test_hltb_lookup_by_title_returns_404_when_no_match(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module.hltb, "fetch_estimated_hours", lambda title, mode: None)
    res = client.post("/api/hltb/lookup", json={"title": "Totally Made Up Game Xyz", "mode": "main"})
    assert res.status_code == 404
    assert res.get_json()["code"] == "no_match"


def test_hltb_lookup_by_title_returns_404_when_title_blank(client):
    res = client.post("/api/hltb/lookup", json={"title": "  ", "mode": "main"})
    assert res.status_code == 404
    assert res.get_json()["code"] == "no_match"


def test_hltb_lookup_by_title_rejects_invalid_mode(client):
    res = client.post("/api/hltb/lookup", json={"title": "Celeste", "mode": "not-a-real-mode"})
    assert res.status_code == 400
