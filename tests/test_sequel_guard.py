import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_extract_sequel_number_roman_and_arabic():
    from backend.sequel_guard import extract_sequel_number
    assert extract_sequel_number("dark souls ii") == 2
    assert extract_sequel_number("dark souls iii") == 3
    assert extract_sequel_number("watch dogs 2") == 2
    assert extract_sequel_number("metal gear solid v the phantom pain") == 5
    assert extract_sequel_number("kingdom hearts iii re mind") == 3
    assert extract_sequel_number("the legend of zelda breath of the wild") is None
    assert extract_sequel_number("nier automata a") is None
    assert extract_sequel_number("") is None
    assert extract_sequel_number(None) is None


def test_sequel_conflict_only_when_both_sides_have_different_numbers():
    from backend.sequel_guard import sequel_conflict
    assert sequel_conflict("dark souls ii", "dark souls iii") is True
    assert sequel_conflict("dark souls ii", "dark souls ii") is False
    assert sequel_conflict("dark souls", "dark souls ii") is False  # one side has no marker
    assert sequel_conflict("celeste", "hades") is False


def test_cover_search_similarity_penalizes_sequel_mismatch():
    from backend.covers import _similarity
    same_ratio = _similarity("Dark Souls II", "Dark Souls II")
    mismatched_ratio = _similarity("Dark Souls II", "Dark Souls III")
    unrelated_ratio = _similarity("Dark Souls II", "Celeste")
    assert same_ratio > mismatched_ratio
    # The whole point of the guard: despite being nearly identical text,
    # "II" vs "III" must rank clearly below a same-title exact match.
    assert mismatched_ratio < same_ratio - 0.3
    assert mismatched_ratio > unrelated_ratio  # still recognizably related text


def test_sanitize_fuzzy_never_suggests_a_different_sequel_entry(monkeypatch):
    import sys as _sys
    for mod in list(_sys.modules):
        if mod.startswith("backend"):
            del _sys.modules[mod]
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BACKLOG_DATA_DIR"] = tmp
        from backend import db as db_module
        db_module.init_db()
        from backend import sanitize

        # Seed a local "canonical" entry for Dark Souls III only, then ask
        # about Dark Souls II — must NOT suggest III despite being close text.
        monkeypatch.setattr(sanitize, "load_aliases", lambda: {"dark souls remastered": "Dark Souls: Remastered"})
        name, source = sanitize.find_canonical_suggestion("Dark Souls III", allow_external=False)
        assert name != "Dark Souls: Remastered" or source is None


def test_review_matching_never_confuses_different_sequel_numbers():
    import sys as _sys
    for mod in list(_sys.modules):
        if mod.startswith("backend"):
            del _sys.modules[mod]
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BACKLOG_DATA_DIR"] = tmp
        from backend import db as db_module
        db_module.init_db()
        from backend.importer import rank_review_candidates

        completed = {"dark souls ii": 1, "dark souls iii": 2}
        # Without the guard this would come back "ambiguous" (ii=1.0 vs
        # iii=0.963, well within the confidence margin) and even risk
        # picking iii — the guard excludes iii entirely since its number
        # disagrees, leaving a single confident, correct match.
        match_type, suggested_id, alts = rank_review_candidates("dark souls ii", completed)
        assert suggested_id == 1
        assert 2 not in ([suggested_id] + alts)
        assert match_type == "fuzzy"
