from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from leaderboard import api as leaderboard_api


class FakeCursor:
    def __init__(self):
        self.description = []
        self._one = None
        self._all = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        q = " ".join(query.split())
        self._one = None
        self._all = []

        if "FROM latest" in q and "ORDER BY latest.rating" in q:
            self.description = [
                ("agent_id",),
                ("name",),
                ("faction",),
                ("rating",),
                ("timestamp",),
            ]
            self._all = [
                (
                    "bot-1",
                    "Astra",
                    "simulation",
                    Decimal("612.5"),
                    datetime(2026, 3, 17, 12, 0, 0),
                ),
                (
                    "bot-2",
                    "Vanta",
                    "simulation",
                    Decimal("598.0"),
                    datetime(2026, 3, 17, 12, 0, 0),
                ),
            ]
        elif "GROUP BY a.id, a.name, a.faction" in q:
            self.description = [
                ("agent_id",),
                ("name",),
                ("faction",),
                ("rating",),
                ("timestamp",),
            ]
            self._all = [
                (
                    "bot-1",
                    "Astra",
                    "simulation",
                    Decimal("630.0"),
                    datetime(2026, 3, 17, 12, 0, 0),
                ),
            ]
        elif q.startswith(
            "SELECT id, name, public_key, faction, created_at FROM agents"
        ):
            agent_id = params[0]
            if agent_id == "missing-agent":
                self._one = None
            else:
                self._one = (
                    agent_id,
                    "Astra",
                    "pk_123",
                    "simulation",
                    datetime(2026, 1, 1, 9, 0, 0),
                )
        elif (
            "SELECT power_rank, honor_rank, chaos_rank, influence_rank, timestamp" in q
            and "LIMIT 1" in q
        ):
            self._one = (
                Decimal("610.0"),
                Decimal("590.0"),
                Decimal("520.0"),
                Decimal("605.0"),
                datetime(2026, 3, 17, 12, 0, 0),
            )
        elif "SELECT MAX(power_rank) AS best_power" in q:
            self._one = (
                Decimal("640.0"),
                Decimal("620.0"),
                Decimal("560.0"),
                Decimal("630.0"),
            )
        elif "WITH per_match_max AS" in q:
            self._one = (3, Decimal("89.333"), Decimal("110.000"), 1)
        elif "FROM alliances" in q:
            self._one = (1, 2)
        elif "SELECT m.id, m.type, m.status" in q:
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
                    "mat-1",
                    "resource_race",
                    "completed",
                    datetime(2026, 3, 17, 11, 0, 0),
                    datetime(2026, 3, 17, 11, 5, 0),
                    Decimal("110.0"),
                    {"power": 11.2},
                )
            ]
        elif q.startswith("SELECT 1 FROM agents WHERE id = %s"):
            self._one = None if params[0] == "missing-agent" else (1,)
        elif "WITH recent AS" in q and "FROM leaderboard_snapshots" in q:
            self._all = [
                (
                    Decimal("560.0"),
                    Decimal("550.0"),
                    Decimal("500.0"),
                    Decimal("540.0"),
                    datetime(2026, 3, 16, 12, 0, 0),
                ),
                (
                    Decimal("610.0"),
                    Decimal("590.0"),
                    Decimal("520.0"),
                    Decimal("605.0"),
                    datetime(2026, 3, 17, 12, 0, 0),
                ),
            ]
        else:
            raise AssertionError(f"Unexpected query in test double: {q}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor()


def test_get_leaderboard(monkeypatch):
    monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
    client = TestClient(leaderboard_api.app)

    response = client.get(
        "/leaderboard", params={"type": "power", "season": "current", "limit": 2}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["entries"][0]["position"] == 1
    assert payload["entries"][0]["rating"] == 612.5


def test_get_agent_stats(monkeypatch):
    monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
    client = TestClient(leaderboard_api.app)

    response = client.get("/leaderboard/agent/bot-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"]["id"] == "bot-1"
    assert payload["match_stats"]["total_matches"] == 3
    assert payload["alliances"]["active"] == 1


def test_get_agent_stats_404(monkeypatch):
    monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
    client = TestClient(leaderboard_api.app)

    response = client.get("/leaderboard/agent/missing-agent")

    assert response.status_code == 404


def test_get_agent_history(monkeypatch):
    monkeypatch.setattr(leaderboard_api, "_connect", lambda: FakeConnection())
    client = TestClient(leaderboard_api.app)

    response = client.get("/leaderboard/agent/bot-1/history", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "bot-1"
    assert payload["points"] == 2
    assert payload["history"][0]["power"] == 560.0
