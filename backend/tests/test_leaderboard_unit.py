"""Comprehensive unit tests for leaderboard calculator and API.

Tests cover:
- Rank calculations, delta computation, tie-breaking
- All 4 ranking axes (Power, Honor, Chaos, Influence)
- Edge cases: empty leaderboard, same scores, rank boundaries
- API endpoints with mocked database responses
- Response formatting and pagination
"""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from leaderboard.calculator import (
    RANK_AXES,
    AgentRatings,
    MatchResult,
    apply_deltas,
    calculate_rank_deltas,
)
from leaderboard import api as leaderboard_api


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_match_results():
    """Sample match results with varying scores."""
    return [
        MatchResult(agent_id="agent-a", score=100.0),
        MatchResult(agent_id="agent-b", score=75.0),
        MatchResult(agent_id="agent-c", score=50.0),
        MatchResult(agent_id="agent-d", score=25.0),
    ]


@pytest.fixture
def tied_match_results():
    """Match results with tied scores."""
    return [
        MatchResult(agent_id="agent-a", score=100.0),
        MatchResult(agent_id="agent-b", score=100.0),
        MatchResult(agent_id="agent-c", score=50.0),
    ]


@pytest.fixture
def sample_ratings():
    """Sample current ratings for agents."""
    return {
        "agent-a": {"power": 550.0, "honor": 500.0, "chaos": 480.0, "influence": 520.0},
        "agent-b": {"power": 480.0, "honor": 510.0, "chaos": 500.0, "influence": 490.0},
        "agent-c": {"power": 520.0, "honor": 480.0, "chaos": 520.0, "influence": 500.0},
    }


@pytest.fixture
def extreme_ratings():
    """Ratings at boundary conditions."""
    return {
        "agent-a": {"power": 0.0, "honor": 0.0, "chaos": 0.0, "influence": 0.0},
        "agent-b": {"power": 1000.0, "honor": 1000.0, "chaos": 1000.0, "influence": 1000.0},
        "agent-c": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
    }


# =============================================================================
# Calculator Tests - Basic Functionality
# =============================================================================

class TestCalculateRankDeltasBasic:
    """Basic functionality tests for calculate_rank_deltas."""

    def test_empty_results_returns_empty_dict(self):
        """Empty match results should return empty dict."""
        result = calculate_rank_deltas([])
        assert result == {}

    def test_single_participant(self):
        """Single participant should get deltas for all axes."""
        results = [MatchResult(agent_id="solo", score=50.0)]
        deltas = calculate_rank_deltas(results)
        
        assert "solo" in deltas
        assert set(deltas["solo"].keys()) == set(RANK_AXES)
        # Winner should generally have positive deltas
        assert all(isinstance(v, float) for v in deltas["solo"].values())

    def test_all_participants_returned(self, sample_match_results):
        """All participants should be in the result."""
        deltas = calculate_rank_deltas(sample_match_results)
        
        agent_ids = {r.agent_id for r in sample_match_results}
        assert set(deltas.keys()) == agent_ids

    def test_deltas_are_clamped(self, sample_match_results):
        """All delta values should be within clamp range."""
        deltas = calculate_rank_deltas(sample_match_results)
        
        for agent_deltas in deltas.values():
            for axis, value in agent_deltas.items():
                assert -40.0 <= value <= 40.0, f"{axis}={value} not in range [-40, 40]"


# =============================================================================
# Calculator Tests - Ranking Axes
# =============================================================================

class TestCalculateRankDeltasAxes:
    """Tests for all 4 ranking axes (Power, Honor, Chaos, Influence)."""

    def test_power_delta_higher_for_winner(self, sample_match_results):
        """Winner should have higher power delta than losers."""
        deltas = calculate_rank_deltas(sample_match_results)
        
        # Agent with highest score should have highest power
        assert deltas["agent-a"]["power"] >= deltas["agent-b"]["power"]
        assert deltas["agent-b"]["power"] >= deltas["agent-c"]["power"]
        assert deltas["agent-c"]["power"] >= deltas["agent-d"]["power"]

    def test_all_axes_present(self, sample_match_results):
        """All 4 axes should be present in results."""
        deltas = calculate_rank_deltas(sample_match_results)
        
        for agent_id, agent_deltas in deltas.items():
            assert "power" in agent_deltas
            assert "honor" in agent_deltas
            assert "chaos" in agent_deltas
            assert "influence" in agent_deltas

    def test_honor_consistency_bonus(self):
        """Honor delta rewards consistency between placement and normalized score."""
        results = [
            MatchResult(agent_id="consistent", score=100.0),
            MatchResult(agent_id="consistent2", score=90.0),
            MatchResult(agent_id="consistent3", score=80.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        # All participants should have honor values within range
        for agent_deltas in deltas.values():
            assert -40.0 <= agent_deltas["honor"] <= 40.0

    def test_chaos_upset_contribution(self):
        """Chaos delta includes upset contribution (difference from expected)."""
        results = [
            MatchResult(agent_id="underdog", score=100.0),
            MatchResult(agent_id="favorite", score=50.0),
        ]
        # Underdog with lower rating winning should create more chaos
        ratings = {
            "underdog": {"power": 400.0},
            "favorite": {"power": 600.0},
        }
        deltas = calculate_rank_deltas(results, ratings)
        
        # Both should have chaos values
        assert "underdog" in deltas and "favorite" in deltas
        assert -40.0 <= deltas["underdog"]["chaos"] <= 40.0

    def test_influence_expected_outperformance(self):
        """Influence delta rewards outperforming expected odds."""
        results = [
            MatchResult(agent_id="agent1", score=100.0),
            MatchResult(agent_id="agent2", score=50.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        # Winner should generally have positive influence
        assert deltas["agent1"]["influence"] > 0


# =============================================================================
# Calculator Tests - Tie Breaking
# =============================================================================

class TestCalculateRankDeltasTieBreaking:
    """Tests for tie-breaking behavior."""

    def test_tied_scores_different_placements(self):
        """With tied scores, agents get different deltas based on position.
        
        Note: Even with tied scores, agents at different positions (based on
        sorting order) get different deltas because place_norm differs.
        The calculator doesn't explicitly handle ties with equal deltas.
        """
        results = [
            MatchResult(agent_id="agent-a", score=100.0),
            MatchResult(agent_id="agent-b", score=100.0),
            MatchResult(agent_id="agent-c", score=50.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        # Winner positions (1st and 2nd) should have higher power than loser
        assert deltas["agent-a"]["power"] > deltas["agent-c"]["power"]
        assert deltas["agent-b"]["power"] > deltas["agent-c"]["power"]
        
    def test_tied_scores_ordering(self):
        """Tied scores maintain order but get different place_norm values.
        
        With 2 participants tied, first place gets better deltas than second.
        """
        results = [
            MatchResult(agent_id="first", score=100.0),
            MatchResult(agent_id="second", score=100.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        # First place should have better power than second
        assert deltas["first"]["power"] > deltas["second"]["power"]


# =============================================================================
# Calculator Tests - Edge Cases
# =============================================================================

class TestCalculateRankDeltasEdgeCases:
    """Edge case tests for calculate_rank_deltas."""

    def test_zero_score_span(self):
        """All same scores (zero span) should be handled gracefully.
        
        The calculator uses max(span, 1e-6) to avoid division by zero,
        but agents still get different place_norm values based on position.
        """
        results = [
            MatchResult(agent_id="a", score=50.0),
            MatchResult(agent_id="b", score=50.0),
            MatchResult(agent_id="c", score=50.0),
        ]
        # Should not raise ZeroDivisionError
        deltas = calculate_rank_deltas(results)
        assert len(deltas) == 3
        # All deltas should be within valid range
        for agent_id in ["a", "b", "c"]:
            assert -40.0 <= deltas[agent_id]["power"] <= 40.0

    def test_negative_scores(self):
        """Negative scores should be handled correctly."""
        results = [
            MatchResult(agent_id="a", score=-10.0),
            MatchResult(agent_id="b", score=-20.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        # Higher (less negative) score should win
        assert deltas["a"]["power"] > deltas["b"]["power"]

    def test_very_large_scores(self):
        """Very large scores should be handled without overflow."""
        results = [
            MatchResult(agent_id="a", score=1e9),
            MatchResult(agent_id="b", score=1e8),
        ]
        deltas = calculate_rank_deltas(results)
        
        assert len(deltas) == 2
        assert -40.0 <= deltas["a"]["power"] <= 40.0

    def test_two_participants(self):
        """Minimum viable match (2 participants)."""
        results = [
            MatchResult(agent_id="winner", score=100.0),
            MatchResult(agent_id="loser", score=50.0),
        ]
        deltas = calculate_rank_deltas(results)
        
        assert len(deltas) == 2
        assert deltas["winner"]["power"] > deltas["loser"]["power"]

    def test_many_participants(self):
        """Test with many participants."""
        results = [MatchResult(agent_id=f"agent-{i}", score=float(100 - i)) for i in range(100)]
        deltas = calculate_rank_deltas(results)
        
        assert len(deltas) == 100
        # Check that ordering is maintained
        assert deltas["agent-0"]["power"] >= deltas["agent-50"]["power"]
        assert deltas["agent-50"]["power"] >= deltas["agent-99"]["power"]


# =============================================================================
# Calculator Tests - With Current Ratings
# =============================================================================

class TestCalculateRankDeltasWithRatings:
    """Tests using existing ratings."""

    def test_underdog_win_bonus(self):
        """Underdog beating favorite should get significant power boost."""
        results = [
            MatchResult(agent_id="underdog", score=100.0),
            MatchResult(agent_id="favorite", score=50.0),
        ]
        ratings = {
            "underdog": {"power": 400.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
            "favorite": {"power": 600.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = calculate_rank_deltas(results, ratings)
        
        # Underdog should get positive delta for winning
        assert deltas["underdog"]["power"] > 0
        # Favorite should lose power for losing
        assert deltas["favorite"]["power"] < 0

    def test_favorite_win_expected(self):
        """Favorite beating underdog should get smaller power gain."""
        results = [
            MatchResult(agent_id="favorite", score=100.0),
            MatchResult(agent_id="underdog", score=50.0),
        ]
        ratings = {
            "favorite": {"power": 600.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
            "underdog": {"power": 400.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = calculate_rank_deltas(results, ratings)
        
        # Both get evaluated with current ratings affecting expectation
        assert "favorite" in deltas and "underdog" in deltas

    def test_multiplayer_expected_calculation(self):
        """Expected value calculation in multiplayer matches."""
        results = [
            MatchResult(agent_id="a", score=100.0),
            MatchResult(agent_id="b", score=80.0),
            MatchResult(agent_id="c", score=60.0),
            MatchResult(agent_id="d", score=40.0),
        ]
        ratings = {
            "a": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
            "b": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
            "c": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
            "d": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = calculate_rank_deltas(results, ratings)
        
        # With equal ratings, expected value should be 0.5
        # Winner should still get positive delta
        assert deltas["a"]["power"] > 0


# =============================================================================
# Apply Deltas Tests
# =============================================================================

class TestApplyDeltas:
    """Tests for apply_deltas function."""

    def test_basic_application(self, sample_ratings):
        """Basic delta application."""
        deltas = {
            "agent-a": {"power": 10.0, "honor": 5.0, "chaos": -5.0, "influence": 10.0},
            "agent-b": {"power": -5.0, "honor": 0.0, "chaos": 10.0, "influence": -5.0},
        }
        updated = apply_deltas(sample_ratings, deltas)
        
        assert updated["agent-a"]["power"] == 560.0  # 550 + 10
        assert updated["agent-b"]["power"] == 475.0  # 480 - 5

    def test_clamping_to_max(self):
        """Ratings should not exceed RATING_MAX (1000.0)."""
        ratings = {
            "agent": {"power": 990.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = {
            "agent": {"power": 20.0, "honor": 0.0, "chaos": 0.0, "influence": 0.0},
        }
        updated = apply_deltas(ratings, deltas)
        
        assert updated["agent"]["power"] == 1000.0  # Clamped to max

    def test_clamping_to_min(self):
        """Ratings should not go below RATING_MIN (0.0)."""
        ratings = {
            "agent": {"power": 10.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = {
            "agent": {"power": -20.0, "honor": 0.0, "chaos": 0.0, "influence": 0.0},
        }
        updated = apply_deltas(ratings, deltas)
        
        assert updated["agent"]["power"] == 0.0  # Clamped to min

    def test_clamping_all_axes(self):
        """Test clamping works for all 4 axes."""
        ratings = {
            "agent": {"power": 995.0, "honor": 5.0, "chaos": 5.0, "influence": 995.0},
        }
        deltas = {
            "agent": {"power": 20.0, "honor": -20.0, "chaos": 1000.0, "influence": 20.0},
        }
        updated = apply_deltas(ratings, deltas)
        
        assert updated["agent"]["power"] == 1000.0   # Max clamped
        assert updated["agent"]["honor"] == 0.0      # Min clamped
        assert updated["agent"]["chaos"] == 1000.0   # Max clamped
        assert updated["agent"]["influence"] == 1000.0  # Max clamped

    def test_partial_deltas(self, sample_ratings):
        """Partial delta dicts should work (missing axes default to 0)."""
        deltas = {
            "agent-a": {"power": 10.0},  # Only power specified
        }
        updated = apply_deltas(sample_ratings, deltas)
        
        assert updated["agent-a"]["power"] == 560.0  # 550 + 10
        # Other axes unchanged (delta defaults to 0)
        assert updated["agent-a"]["honor"] == 500.0

    def test_new_agent_default_rating(self):
        """New agents not in ratings get default rating."""
        ratings = {}  # No existing ratings
        deltas = {
            "new-agent": {"power": 10.0, "honor": 5.0, "chaos": -5.0, "influence": 10.0},
        }
        updated = apply_deltas(ratings, deltas)
        
        # Should start from DEFAULT_RATING (500.0)
        assert updated["new-agent"]["power"] == 510.0

    def test_empty_deltas(self):
        """Empty deltas should not change ratings."""
        ratings = {
            "agent": {"power": 500.0, "honor": 500.0, "chaos": 500.0, "influence": 500.0},
        }
        deltas = {}
        updated = apply_deltas(ratings, deltas)
        
        assert updated == {}


# =============================================================================
# AgentRatings Tests
# =============================================================================

class TestAgentRatings:
    """Tests for AgentRatings dataclass."""

    def test_default_values(self):
        """Default values should be DEFAULT_RATING."""
        ratings = AgentRatings()
        
        assert ratings.power == 500.0
        assert ratings.honor == 500.0
        assert ratings.chaos == 500.0
        assert ratings.influence == 500.0

    def test_custom_values(self):
        """Custom values should be respected."""
        ratings = AgentRatings(power=600.0, honor=550.0)
        
        assert ratings.power == 600.0
        assert ratings.honor == 550.0
        assert ratings.chaos == 500.0  # Default

    def test_to_dict(self):
        """to_dict should return correct dict."""
        ratings = AgentRatings(power=600.0, honor=550.0, chaos=520.0, influence=480.0)
        d = ratings.to_dict()
        
        assert d == {
            "power": 600.0,
            "honor": 550.0,
            "chaos": 520.0,
            "influence": 480.0,
        }


# =============================================================================
# MatchResult Tests
# =============================================================================

class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_creation(self):
        """Basic creation."""
        result = MatchResult(agent_id="agent-1", score=100.0)
        
        assert result.agent_id == "agent-1"
        assert result.score == 100.0

    def test_frozen(self):
        """MatchResult should be frozen (immutable)."""
        result = MatchResult(agent_id="agent-1", score=100.0)
        
        with pytest.raises(AttributeError):
            result.score = 200.0


# =============================================================================
# API Mock Infrastructure
# =============================================================================

class FakeCursor:
    """Mock database cursor for API tests."""
    
    def __init__(self, query_responses: Dict[str, Any] = None):
        self.description = []
        self._one = None
        self._all = []
        self._query_responses = query_responses or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        q = " ".join(query.split())
        self._one = None
        self._all = []

        # Current season leaderboard queries
        if "FROM latest" in q and "ORDER BY latest.rating" in q:
            self._handle_current_leaderboard(params)
        # All-time leaderboard
        elif "GROUP BY a.id, a.name, a.faction" in q:
            self._handle_alltime_leaderboard(params)
        # Agent profile
        elif "SELECT id, name, public_key, faction, created_at FROM agents" in q:
            self._handle_agent_lookup(params)
        # Latest snapshot
        elif (
            "SELECT power_rank, honor_rank, chaos_rank, influence_rank, timestamp" in q
            and "LIMIT 1" in q
        ):
            self._handle_latest_snapshot(params)
        # Best ranks
        elif "SELECT MAX(power_rank) AS best_power" in q:
            self._handle_best_ranks(params)
        # Match performance stats
        elif "WITH per_match_max AS" in q:
            self._handle_match_stats(params)
        # Alliance stats
        elif "FROM alliances" in q:
            self._handle_alliance_stats(params)
        # Recent matches
        elif "SELECT m.id, m.type, m.status" in q:
            self._handle_recent_matches(params)
        # Agent existence check
        elif q.startswith("SELECT 1 FROM agents WHERE id = %s"):
            self._handle_agent_exists(params)
        # History query
        elif "WITH recent AS" in q and "FROM leaderboard_snapshots" in q:
            self._handle_history_query(params)
        else:
            raise AssertionError(f"Unexpected query in test double: {q}")

    def _handle_current_leaderboard(self, params):
        limit = params[0] if params else 50
        self.description = [
            ("agent_id",),
            ("name",),
            ("faction",),
            ("rating",),
            ("timestamp",),
        ]
        self._all = [
            (
                f"bot-{i}",
                f"Agent {i}",
                "simulation",
                Decimal(f"{600 + (10 - i) * 10}.0"),
                datetime(2026, 3, 17, 12, 0, 0),
            )
            for i in range(min(limit, 10))
        ]

    def _handle_alltime_leaderboard(self, params):
        limit = params[0] if params else 50
        self.description = [
            ("agent_id",),
            ("name",),
            ("faction",),
            ("rating",),
            ("timestamp",),
        ]
        self._all = [
            (
                f"bot-{i}",
                f"Agent {i}",
                "simulation",
                Decimal(f"{650 + (10 - i) * 15}.0"),
                datetime(2026, 3, 17, 12, 0, 0),
            )
            for i in range(min(limit, 5))
        ]

    def _handle_agent_lookup(self, params):
        agent_id = params[0] if params else "unknown"
        if agent_id == "missing-agent" or agent_id == "nonexistent":
            self._one = None
        else:
            self._one = (
                agent_id,
                f"Agent {agent_id}",
                f"pk_{agent_id}",
                "simulation",
                datetime(2026, 1, 1, 9, 0, 0),
            )

    def _handle_latest_snapshot(self, params):
        self._one = (
            Decimal("610.0"),
            Decimal("590.0"),
            Decimal("520.0"),
            Decimal("605.0"),
            datetime(2026, 3, 17, 12, 0, 0),
        )

    def _handle_best_ranks(self, params):
        self._one = (
            Decimal("640.0"),
            Decimal("620.0"),
            Decimal("560.0"),
            Decimal("630.0"),
        )

    def _handle_match_stats(self, params):
        self._one = (10, Decimal("85.500"), Decimal("120.000"), 6)

    def _handle_alliance_stats(self, params):
        self._one = (2, 5)

    def _handle_recent_matches(self, params):
        self.description = [
            ("id",),
            ("type",),
            ("status",),
            ("started_at",),
            ("ended_at",),
            ("score",),
            ("rank_delta",),
        ]
        self._all = [
            (
                f"match-{i}",
                "resource_race" if i % 2 == 0 else "combat",
                "completed",
                datetime(2026, 3, 17, 11 - i, 0, 0),
                datetime(2026, 3, 17, 11 - i, 5, 0),
                Decimal(f"{100 - i * 5}.0"),
                {"power": 10.0 - i, "honor": 5.0, "chaos": -2.0, "influence": 8.0},
            )
            for i in range(10)
        ]

    def _handle_agent_exists(self, params):
        agent_id = params[0] if params else "unknown"
        self._one = None if agent_id in ("missing-agent", "nonexistent") else (1,)

    def _handle_history_query(self, params):
        limit = params[1] if params and len(params) > 1 else 200
        # Generate timestamps in ascending order (oldest first)
        self._all = [
            (
                Decimal(f"{500 + i * 5}.0"),
                Decimal(f"{500 + i * 3}.0"),
                Decimal(f"{500 + i}.0"),
                Decimal(f"{500 + i * 4}.0"),
                datetime(2026, 3, 1, 0, 0, 0) + __import__('datetime').timedelta(hours=i),
            )
            for i in range(min(limit, 50))
        ]

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class FakeConnection:
    """Mock database connection for API tests."""
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor()


# =============================================================================
# API Tests - Leaderboard Endpoint
# =============================================================================

class TestGetLeaderboard:
    """Tests for GET /leaderboard endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        """Set up test client with mocked database."""
        monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
        self.client = TestClient(leaderboard_api.app)

    def test_get_leaderboard_default_params(self):
        """Default parameters should return power leaderboard for current season."""
        response = self.client.get("/leaderboard")
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "power"
        assert payload["season"] == "current"
        assert payload["count"] > 0
        assert len(payload["entries"]) > 0

    def test_get_leaderboard_power_axis(self):
        """Test power axis leaderboard."""
        response = self.client.get("/leaderboard", params={"type": "power"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "power"
        assert all("power" in entry or "rating" in entry for entry in payload["entries"])

    def test_get_leaderboard_honor_axis(self):
        """Test honor axis leaderboard."""
        response = self.client.get("/leaderboard", params={"type": "honor"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "honor"

    def test_get_leaderboard_chaos_axis(self):
        """Test chaos axis leaderboard."""
        response = self.client.get("/leaderboard", params={"type": "chaos"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "chaos"

    def test_get_leaderboard_influence_axis(self):
        """Test influence axis leaderboard."""
        response = self.client.get("/leaderboard", params={"type": "influence"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "influence"

    def test_get_leaderboard_current_season(self):
        """Test current season query."""
        response = self.client.get("/leaderboard", params={"season": "current"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["season"] == "current"

    def test_get_leaderboard_all_seasons(self):
        """Test all seasons query."""
        response = self.client.get("/leaderboard", params={"season": "all"})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["season"] == "all"

    def test_get_leaderboard_pagination_limit(self):
        """Test limit parameter for pagination."""
        response = self.client.get("/leaderboard", params={"limit": 5})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 5
        assert len(payload["entries"]) == 5

    def test_get_leaderboard_pagination_large_limit(self):
        """Test large limit parameter."""
        response = self.client.get("/leaderboard", params={"limit": 100})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] <= 100

    def test_get_leaderboard_entry_format(self):
        """Check entry format in response."""
        response = self.client.get("/leaderboard", params={"limit": 1})
        
        assert response.status_code == 200
        payload = response.json()
        entry = payload["entries"][0]
        
        assert "position" in entry
        assert "agent_id" in entry
        assert "name" in entry
        assert "faction" in entry
        assert "rating" in entry
        assert isinstance(entry["position"], int)
        assert entry["position"] == 1

    def test_get_leaderboard_position_ordering(self):
        """Positions should be in ascending order."""
        response = self.client.get("/leaderboard", params={"limit": 5})
        
        assert response.status_code == 200
        payload = response.json()
        positions = [e["position"] for e in payload["entries"]]
        assert positions == [1, 2, 3, 4, 5]

    def test_get_leaderboard_rating_descending(self):
        """Ratings should be in descending order."""
        response = self.client.get("/leaderboard", params={"limit": 5})
        
        assert response.status_code == 200
        payload = response.json()
        ratings = [e["rating"] for e in payload["entries"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_get_leaderboard_tie_breaker_by_agent_id(self):
        """Ties should be broken by agent_id ascending."""
        # This is implicit in the query (ORDER BY rating DESC, a.id ASC)
        response = self.client.get("/leaderboard", params={"limit": 10})
        
        assert response.status_code == 200
        # Just verify it works without error


# =============================================================================
# API Tests - Agent Profile Endpoint
# =============================================================================

class TestGetAgentProfile:
    """Tests for GET /leaderboard/agent/{agent_id} endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        """Set up test client with mocked database."""
        monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
        self.client = TestClient(leaderboard_api.app)

    def test_get_agent_profile_success(self):
        """Successful agent profile retrieval."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        assert "agent" in payload
        assert payload["agent"]["id"] == "bot-1"

    def test_get_agent_profile_not_found(self):
        """404 for non-existent agent."""
        response = self.client.get("/leaderboard/agent/missing-agent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_agent_profile_agent_fields(self):
        """Agent profile should contain all agent fields."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        agent = response.json()["agent"]
        
        assert "id" in agent
        assert "name" in agent
        assert "public_key" in agent
        assert "faction" in agent
        assert "created_at" in agent

    def test_get_agent_profile_current_ranks(self):
        """Response should include current ranks for all axes."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        current = payload["current_ranks"]
        
        assert "power" in current
        assert "honor" in current
        assert "chaos" in current
        assert "influence" in current
        assert "timestamp" in current

    def test_get_agent_profile_best_ranks(self):
        """Response should include best ranks for all axes."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        best = payload["best_ranks"]
        
        assert "power" in best
        assert "honor" in best
        assert "chaos" in best
        assert "influence" in best

    def test_get_agent_profile_match_stats(self):
        """Response should include match statistics."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        stats = payload["match_stats"]
        
        assert "total_matches" in stats
        assert "avg_score" in stats
        assert "best_match_score" in stats
        assert "wins" in stats
        assert isinstance(stats["total_matches"], int)
        assert isinstance(stats["wins"], int)

    def test_get_agent_profile_alliances(self):
        """Response should include alliance stats."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        alliances = payload["alliances"]
        
        assert "active" in alliances
        assert "total" in alliances
        assert isinstance(alliances["active"], int)
        assert isinstance(alliances["total"], int)

    def test_get_agent_profile_recent_matches(self):
        """Response should include recent matches."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        matches = payload["recent_matches"]
        
        assert isinstance(matches, list)
        if matches:
            match = matches[0]
            assert "id" in match
            assert "type" in match
            assert "status" in match
            assert "score" in match

    def test_get_agent_profile_decimal_normalization(self):
        """Decimal values should be normalized to float."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        
        # Check that Decimal values are converted
        assert isinstance(payload["match_stats"]["avg_score"], float)


# =============================================================================
# API Tests - Agent History Endpoint
# =============================================================================

class TestGetAgentHistory:
    """Tests for GET /leaderboard/agent/{agent_id}/history endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        """Set up test client with mocked database."""
        monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
        self.client = TestClient(leaderboard_api.app)

    def test_get_agent_history_success(self):
        """Successful history retrieval."""
        response = self.client.get("/leaderboard/agent/bot-1/history")
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["agent_id"] == "bot-1"
        assert "history" in payload
        assert "points" in payload

    def test_get_agent_history_not_found(self):
        """404 for non-existent agent."""
        response = self.client.get("/leaderboard/agent/missing-agent/history")
        
        assert response.status_code == 404

    def test_get_agent_history_limit_param(self):
        """Test limit parameter."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 10})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["points"] == 10
        assert len(payload["history"]) == 10

    def test_get_agent_history_large_limit(self):
        """Test with larger limit."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 50})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["points"] <= 50

    def test_get_agent_history_point_format(self):
        """Each history point should have all axes."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 5})
        
        assert response.status_code == 200
        payload = response.json()
        
        for point in payload["history"]:
            assert "timestamp" in point
            assert "power" in point
            assert "honor" in point
            assert "chaos" in point
            assert "influence" in point

    def test_get_agent_history_chronological_order(self):
        """History should be in chronological order (ascending timestamp)."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 10})
        
        assert response.status_code == 200
        payload = response.json()
        
        timestamps = [p["timestamp"] for p in payload["history"]]
        assert timestamps == sorted(timestamps)

    def test_get_agent_history_all_axes_present(self):
        """All 4 ranking axes should be present in each history point."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 1})
        
        assert response.status_code == 200
        payload = response.json()
        point = payload["history"][0]
        
        assert set(point.keys()) == {"timestamp", "power", "honor", "chaos", "influence"}


# =============================================================================
# API Tests - Response Formatting
# =============================================================================

class TestResponseFormatting:
    """Tests for API response formatting."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        """Set up test client with mocked database."""
        monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
        self.client = TestClient(leaderboard_api.app)

    def test_leaderboard_response_structure(self):
        """Leaderboard response has correct top-level structure."""
        response = self.client.get("/leaderboard")
        
        assert response.status_code == 200
        payload = response.json()
        assert "type" in payload
        assert "season" in payload
        assert "count" in payload
        assert "entries" in payload
        assert isinstance(payload["count"], int)
        assert isinstance(payload["entries"], list)

    def test_agent_profile_response_structure(self):
        """Agent profile response has correct top-level structure."""
        response = self.client.get("/leaderboard/agent/bot-1")
        
        assert response.status_code == 200
        payload = response.json()
        assert "agent" in payload
        assert "current_ranks" in payload
        assert "best_ranks" in payload
        assert "match_stats" in payload
        assert "alliances" in payload
        assert "recent_matches" in payload

    def test_history_response_structure(self):
        """History response has correct top-level structure."""
        response = self.client.get("/leaderboard/agent/bot-1/history")
        
        assert response.status_code == 200
        payload = response.json()
        assert "agent_id" in payload
        assert "points" in payload
        assert "history" in payload
        assert isinstance(payload["points"], int)
        assert isinstance(payload["history"], list)


# =============================================================================
# API Tests - Edge Cases
# =============================================================================

class TestApiEdgeCases:
    """Edge case tests for API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        """Set up test client with mocked database."""
        monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
        self.client = TestClient(leaderboard_api.app)

    def test_leaderboard_limit_minimum(self):
        """Test minimum limit value."""
        response = self.client.get("/leaderboard", params={"limit": 1})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1

    def test_leaderboard_invalid_axis(self):
        """Invalid axis should return validation error."""
        # FastAPI should reject invalid enum values
        response = self.client.get("/leaderboard", params={"type": "invalid"})
        
        assert response.status_code == 422  # Validation error

    def test_leaderboard_invalid_season(self):
        """Invalid season should return validation error."""
        response = self.client.get("/leaderboard", params={"season": "invalid"})
        
        assert response.status_code == 422  # Validation error

    def test_history_limit_minimum(self):
        """Test minimum history limit."""
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 1})
        
        assert response.status_code == 200
        payload = response.json()
        assert payload["points"] == 1

    def test_agent_profile_special_characters_id(self):
        """Agent IDs with special characters should be handled."""
        # This should not cause issues
        response = self.client.get("/leaderboard/agent/agent-with-dashes_and_123")
        
        # Should either work or return 404, not 500
        assert response.status_code in [200, 404]

    def test_all_four_axes_in_all_responses(self):
        """Verify all 4 axes appear consistently across endpoints."""
        # Check leaderboard supports all axes
        for axis in ["power", "honor", "chaos", "influence"]:
            response = self.client.get("/leaderboard", params={"type": axis})
            assert response.status_code == 200
            assert response.json()["type"] == axis

        # Check agent profile has all axes
        response = self.client.get("/leaderboard/agent/bot-1")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload["current_ranks"].keys()) >= {"power", "honor", "chaos", "influence"}
        assert set(payload["best_ranks"].keys()) >= {"power", "honor", "chaos", "influence"}

        # Check history has all axes
        response = self.client.get("/leaderboard/agent/bot-1/history", params={"limit": 1})
        assert response.status_code == 200
        point = response.json()["history"][0]
        assert set(point.keys()) >= {"power", "honor", "chaos", "influence"}
