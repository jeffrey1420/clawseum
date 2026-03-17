from __future__ import annotations

import json

import pytest


def test_load_bot_agents_from_file(simulation_module, sample_agents, tmp_path):
    agents_file = tmp_path / "agents.json"
    agents_file.write_text(json.dumps(sample_agents))

    sim = simulation_module.ArenaSimulation(seed=42)
    agents = sim.load_bot_agents(agents_file=str(agents_file))

    assert len(agents) == len(sample_agents)
    assert agents[0].agent_id == sample_agents[0]["agent_id"]
    assert all(
        set(agent.ranks.keys()) == set(simulation_module.RANK_KEYS) for agent in agents
    )


def test_load_bot_agents_rejects_invalid_count(simulation_module):
    sim = simulation_module.ArenaSimulation(seed=7)

    with pytest.raises(ValueError):
        sim.load_bot_agents(count=3)


def test_choose_action_prefers_deposit_when_threshold_met(
    simulation_module, monkeypatch
):
    sim = simulation_module.ArenaSimulation(seed=1)
    agent = simulation_module.BotAgent(
        agent_id="bot-1", name="Alpha", strategy="balanced"
    )
    me = simulation_module.AgentRoundState(carried=5)

    all_state = {
        "bot-1": me,
        "bot-2": simulation_module.AgentRoundState(),
    }
    agents = [
        agent,
        simulation_module.BotAgent(agent_id="bot-2", name="Beta", strategy="greedy"),
    ]
    nodes = [simulation_module.ResourceNode(node_id="alpha", remaining=20)]

    monkeypatch.setattr(sim.random, "random", lambda: 0.2)

    action = sim._choose_action(agent, me, all_state, agents, nodes)

    assert action == {"type": "deposit"}


def test_run_resource_race_round_outputs_ranked_result(
    simulation_module, sample_agents, tmp_path
):
    agents_file = tmp_path / "agents.json"
    agents_file.write_text(json.dumps(sample_agents[:4]))

    sim = simulation_module.ArenaSimulation(seed=123)
    agents = sim.load_bot_agents(agents_file=str(agents_file))
    result = sim.run_resource_race_round(agents, ticks=10)

    standings = result["standings"]
    assert [row["placement"] for row in standings] == [1, 2, 3, 4]
    assert len(result["rank_updates"]) == 4

    scores = [row["mission_score"] for row in standings]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    event_types = {event["type"] for event in result["events"]}
    assert {"mission_started", "mission_scored", "ranks_updated"}.issubset(event_types)

    for update in result["rank_updates"]:
        for axis in simulation_module.RANK_KEYS:
            assert 0 <= update["after"][axis] <= 1000
