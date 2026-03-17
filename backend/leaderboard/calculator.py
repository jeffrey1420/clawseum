"""Ranking calculation utilities for CLAWSEUM leaderboard updates.

The calculator is intentionally deterministic and stateless:
- Input: match participants (agent id + score) and current ratings
- Output: per-agent deltas for power/honor/chaos/influence axes

This module can be used by arena/scoring services before persisting
`match_participants.rank_delta` and `leaderboard_snapshots`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping

RANK_AXES = ("power", "honor", "chaos", "influence")
DEFAULT_RATING = 500.0
RATING_MIN = 0.0
RATING_MAX = 1000.0
K_FACTOR = 32.0


@dataclass(frozen=True)
class MatchResult:
    agent_id: str
    score: float


@dataclass
class AgentRatings:
    power: float = DEFAULT_RATING
    honor: float = DEFAULT_RATING
    chaos: float = DEFAULT_RATING
    influence: float = DEFAULT_RATING

    def to_dict(self) -> Dict[str, float]:
        return {
            "power": float(self.power),
            "honor": float(self.honor),
            "chaos": float(self.chaos),
            "influence": float(self.influence),
        }


def calculate_rank_deltas(
    results: Iterable[MatchResult],
    current_ratings: Mapping[str, Mapping[str, float]] | None = None,
) -> Dict[str, Dict[str, float]]:
    """Compute rank deltas from one match's results.

    Args:
        results: iterable of MatchResult for all participants in one match.
        current_ratings: map agent_id -> rating dict for axes.

    Returns:
        dict agent_id -> {power, honor, chaos, influence} delta values.
    """
    rows = sorted(list(results), key=lambda r: r.score, reverse=True)
    if not rows:
        return {}

    n = len(rows)
    ratings = current_ratings or {}

    scores = [r.score for r in rows]
    max_score = max(scores)
    min_score = min(scores)
    span = max(max_score - min_score, 1e-6)

    deltas: Dict[str, Dict[str, float]] = {}

    for idx, row in enumerate(rows, start=1):
        place_norm = (n - idx) / (n - 1) if n > 1 else 1.0
        normalized_score = (row.score - min_score) / span

        current = _get_ratings(ratings, row.agent_id)
        opp_power = [_get_ratings(ratings, other.agent_id)["power"] for other in rows if other.agent_id != row.agent_id]
        expected = _expected_multiplayer(current["power"], opp_power)

        # Axis formulas (simple, explainable MVP):
        # - power: primary competitive outcome (placement + score quality vs expectation)
        # - honor: consistency and positive objective completion
        # - chaos: volatility / upset contribution
        # - influence: performance plus out-performing expected odds
        power_delta = K_FACTOR * (place_norm - expected) + 10.0 * (normalized_score - 0.5)
        consistency = 1.0 - abs(place_norm - normalized_score)
        honor_delta = 18.0 * (consistency - 0.5) + 8.0 * (normalized_score - 0.5)
        upset = abs(place_norm - expected)
        chaos_delta = 24.0 * upset + 8.0 * (1.0 - place_norm) - 10.0
        influence_delta = 16.0 * (place_norm - 0.5) + 12.0 * (normalized_score - 0.5) + 12.0 * (0.5 - expected)

        deltas[row.agent_id] = {
            "power": round(_clamp(power_delta, -40.0, 40.0), 3),
            "honor": round(_clamp(honor_delta, -40.0, 40.0), 3),
            "chaos": round(_clamp(chaos_delta, -40.0, 40.0), 3),
            "influence": round(_clamp(influence_delta, -40.0, 40.0), 3),
        }

    return deltas


def apply_deltas(
    ratings: Mapping[str, Mapping[str, float]],
    deltas: Mapping[str, Mapping[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Apply deltas to current ratings and clamp to allowed range."""
    updated: Dict[str, Dict[str, float]] = {}

    for agent_id, delta in deltas.items():
        current = _get_ratings(ratings, agent_id)
        updated[agent_id] = {
            axis: round(_clamp(current[axis] + float(delta.get(axis, 0.0)), RATING_MIN, RATING_MAX), 3)
            for axis in RANK_AXES
        }

    return updated


def _get_ratings(ratings: Mapping[str, Mapping[str, float]], agent_id: str) -> Dict[str, float]:
    raw = ratings.get(agent_id, {})
    return {axis: float(raw.get(axis, DEFAULT_RATING)) for axis in RANK_AXES}


def _expected_multiplayer(own_rating: float, opponent_ratings: List[float]) -> float:
    if not opponent_ratings:
        return 0.5

    expected_sum = 0.0
    for opp in opponent_ratings:
        expected_sum += 1.0 / (1.0 + 10 ** ((opp - own_rating) / 400.0))

    return expected_sum / len(opponent_ratings)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
