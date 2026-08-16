"""Computes statistics for the dashboard and for 'My Year Review'."""
import random
from collections import defaultdict
from .db import get_conn

MONTHS = ["Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
          "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Décembre"]


def _fetch_all():
    conn = get_conn()
    completed = [dict(r) for r in conn.execute("SELECT * FROM games WHERE status='completed'").fetchall()]
    backlog = [dict(r) for r in conn.execute("SELECT * FROM games WHERE status='backlog'").fetchall()]
    conn.close()
    return completed, backlog


def _pick_extreme(games, key, want_max):
    """Returns the most/least extreme game according to `key`. In case of
    a tie between several games, picks one at random rather than always the
    first one found (less static / fairer result)."""
    valid = [g for g in games if g.get(key) not in (None, 0)]
    if not valid:
        return None
    extreme_val = max(g[key] for g in valid) if want_max else min(g[key] for g in valid)
    tied = [g for g in valid if g[key] == extreme_val]
    return random.choice(tied)


def _game_ref(g, extra_key=None):
    if not g:
        return None
    ref = {"id": g["id"], "title": g["title"], "cover_path": g.get("cover_path")}
    if extra_key:
        ref[extra_key] = g.get(extra_key)
    return ref


def compute_stats(year=None):
    """year (optional) restricts only the rating distribution and monthly
    trend to a given year; the rest of the dashboard stays an overview, so
    filtering just those two charts doesn't make the whole dashboard feel
    like it changed."""
    completed, backlog = _fetch_all()

    total_hours = sum(g["hours_played"] or 0 for g in completed)
    nb_completed = len(completed)
    avg_hours_per_game = round(total_hours / nb_completed, 1) if nb_completed else 0

    ratings = [g["rating"] for g in completed if g["rating"] not in (None, 0)]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    # Breakdown by year (+ cumulative, for a progress chart) — never filtered
    by_year = defaultdict(lambda: {"nb": 0, "hours": 0.0})
    for g in completed:
        y = g["year_finished"] or "Inconnu"
        by_year[y]["nb"] += 1
        by_year[y]["hours"] += g["hours_played"] or 0
    years_sorted = sorted(by_year.keys(), key=lambda x: (x == "Inconnu", x))
    by_year_list = []
    cumulative = 0
    for y in years_sorted:
        cumulative += by_year[y]["nb"]
        by_year_list.append({"year": y, "nb": by_year[y]["nb"],
                              "hours": round(by_year[y]["hours"], 1), "cumulative": cumulative})

    nb_years = len([y for y in by_year.keys() if y != "Inconnu"])
    avg_games_per_year = round(nb_completed / nb_years, 2) if nb_years else None

    # Games used for the 2 filterable charts (month / ratings)
    filtered = [g for g in completed if g["year_finished"] == year] if year else completed

    by_month = defaultdict(int)
    for g in filtered:
        if g["month_finished"]:
            by_month[g["month_finished"]] += 1
    by_month_list = [{"month": m, "nb": by_month.get(m, 0)} for m in MONTHS
                      if by_month.get(m, 0) or m in by_month]

    # Rating histogram (scale /10; rounded to the nearest integer for
    # visual grouping — the exact value is still used everywhere else:
    # average, best/worst rated...)
    rating_histogram = defaultdict(int)
    for g in filtered:
        if g["rating"]:
            bucket = min(10, max(1, round(g["rating"])))
            rating_histogram[bucket] += 1
    rating_histogram_list = [{"rating": i, "nb": rating_histogram.get(i, 0)} for i in range(1, 11)]

    worth_it = defaultdict(int)
    for g in completed:
        if g["worth_it"]:
            worth_it[g["worth_it"].strip()] += 1

    nb_dlc = len([g for g in completed if g["dlc"]])
    nb_base_games = nb_completed - nb_dlc

    # Ownership: only makes sense for the backlog (a finished game was, by
    # definition, owned at the time it was played — tracking ownership for
    # completed games adds nothing and was confusing).
    owned = len([g for g in backlog if g["available"] == 1])
    not_owned = len([g for g in backlog if g["available"] == 0])
    unknown = len(backlog) - owned - not_owned
    ownership_backlog = {"owned": owned, "not_owned": not_owned, "unknown": unknown}

    # Highlights (ties resolved at random)
    longest_game = _pick_extreme(completed, "hours_played", want_max=True)
    shortest_game = _pick_extreme(completed, "hours_played", want_max=False)
    best_rated_game = _pick_extreme(completed, "rating", want_max=True)
    worst_rated_game = _pick_extreme(completed, "rating", want_max=False)

    backlog_hours = sum(g["hours_estimated"] or 0 for g in backlog)
    nb_backlog = len(backlog)

    # Pace: how many hours/month have been played on average, and — at
    # that pace — how long the current backlog would take to clear. Uses
    # distinct (year, month) pairs actually represented in the completed
    # games, not just a flat "total months since first game", so a gap
    # year with zero completions doesn't quietly drag the average down.
    active_year_months = {(g["year_finished"], g["month_finished"])
                           for g in completed if g["year_finished"] and g["month_finished"]}
    nb_active_months = len(active_year_months)
    avg_hours_per_month = round(total_hours / nb_active_months, 1) if nb_active_months else None
    months_to_clear_backlog = (
        round(backlog_hours / avg_hours_per_month, 1)
        if avg_hours_per_month and backlog_hours else None
    )

    # DLC still sitting in the backlog, for a fuller "how many DLC" picture
    # alongside the already-completed DLC count below.
    nb_dlc_backlog = len([g for g in backlog if g["dlc"]])

    return {
        "total_hours_played": round(total_hours, 1),
        "nb_completed": nb_completed,
        "avg_hours_per_game": avg_hours_per_game,
        "avg_rating": avg_rating,
        "avg_games_per_year": avg_games_per_year,
        "by_year": by_year_list,
        "by_month": by_month_list,
        "worth_it_distribution": dict(worth_it),
        "rating_histogram": rating_histogram_list,
        "dlc": {"nb_dlc": nb_dlc, "nb_base_games": nb_base_games, "nb_dlc_backlog": nb_dlc_backlog},
        "ownership": {"backlog": ownership_backlog},
        "longest_game": _game_ref(longest_game, "hours_played"),
        "shortest_game": _game_ref(shortest_game, "hours_played"),
        "best_rated_game": _game_ref(best_rated_game, "rating"),
        "worst_rated_game": _game_ref(worst_rated_game, "rating"),
        "backlog": {
            "nb_games": nb_backlog,
            "estimated_hours": round(backlog_hours, 1),
        },
        "pace": {
            "avg_hours_per_month": avg_hours_per_month,
            "months_to_clear_backlog": months_to_clear_backlog,
        },
        "filtered_year": year,
    }


def list_review_years():
    """Years available for 'My Year Review' (years with at least one finished game)."""
    completed, _ = _fetch_all()
    years = sorted({g["year_finished"] for g in completed if g["year_finished"]}, reverse=True)
    return years


def build_year_review(year: int):
    """Builds the 'Spotify Wrapped'-style annual summary for a given year."""
    completed, _ = _fetch_all()
    games = [g for g in completed if g["year_finished"] == year]
    if not games:
        return None

    total_hours = sum(g["hours_played"] or 0 for g in games)
    ratings = [g["rating"] for g in games if g["rating"]]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    best_rated = _pick_extreme(games, "rating", want_max=True)
    most_played = _pick_extreme(games, "hours_played", want_max=True)
    quickest = _pick_extreme(games, "hours_played", want_max=False)

    reviewed = [g for g in games if g.get("review")]
    longest_review = max(reviewed, key=lambda g: len(g["review"]), default=None)

    nb_dlc = len([g for g in games if g["dlc"]])
    nb_abandoned = len([g for g in games if g.get("abandoned")])

    return {
        "year": year,
        "nb_completed": len(games),
        "total_hours": round(total_hours, 1),
        "avg_rating": avg_rating,
        "best_rated_game": _game_ref(best_rated, "rating"),
        "most_played_game": _game_ref(most_played, "hours_played"),
        "quickest_game": _game_ref(quickest, "hours_played"),
        "longest_review_game": (
            {**_game_ref(longest_review), "review_excerpt": longest_review["review"][:220]}
            if longest_review else None
        ),
        "nb_dlc": nb_dlc,
        "nb_abandoned": nb_abandoned,
        "games": [_game_ref(g) for g in games],
    }
