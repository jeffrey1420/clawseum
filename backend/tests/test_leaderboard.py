from __future__ import annotations

from leaderboard.calculator import MatchResult, apply_deltas, calculate_rank_deltas


def test_calculate_rank_deltas_orders_power_by_result():
    results = [
        MatchResult(agent_id="a", score=100.0),
        MatchResult(agent_id="b", score=80.0),
        MatchResult(agent_id="c", score=50.0),
    ]

    deltas = calculate_rank_deltas(results)

    assert set(deltas.keys()) == {"a", "b", "c"}
    assert deltas["a"]["power"] >= deltas["b"]["power"] >= deltas["c"]["power"]


def test_calculate_rank_deltas_empty_results():
    assert calculate_rank_deltas([]) == {}


def test_calculate_rank_deltas_is_deterministic(sample_matches):
    participants = sample_matches[0]["participants"]
    results = [
        MatchResult(agent_id=row["agent_id"], score=row["score"])
        for row in participants
    ]

    first = calculate_rank_deltas(results)
    second = calculate_rank_deltas(results)

    assert first == second


def test_apply_deltas_clamps_rating_range():
    ratings = {
        "a": {"power": 995.0, "honor": 5.0, "chaos": 500.0, "influence": 999.0},
    }
    deltas = {
        "a": {"power": 20.0, "honor": -20.0, "chaos": 600.0, "influence": 5.0},
    }

    updated = apply_deltas(ratings, deltas)

    assert updated["a"]["power"] == 1000.0
    assert updated["a"]["honor"] == 0.0
    assert updated["a"]["chaos"] == 1000.0
    assert updated["a"]["influence"] == 1000.0
