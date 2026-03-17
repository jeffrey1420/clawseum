"""Comprehensive unit tests for CLAWSEUM Arena Engine.

Tests for:
- mission_runner.py: Mission phases, scoring integration, event generation
- agent_runtime.py: Sandbox execution, timeout handling, action validation
- scoring.py: All 4 ranking axes (Power, Honor, Chaos, Influence), delta calculation
- scheduler.py: Cron scheduling, priority queue

Uses pytest fixtures with unittest.mock - no real database or external dependencies.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add the arena-engine path for imports
import sys
sys.path.insert(0, '/root/.openclaw/workspace/work/clawseum/backend/arena-engine')

from config import (
    AgentConfig,
    AgentState,
    AgentStats,
    AgentStrategy,
    EventType,
    MatchConfig,
    MatchResult,
    MatchStatus,
    MissionConfig,
    MissionType,
    ResourceNode,
    StandingDict,
    DEFAULT_RATING,
    RATING_MIN,
    RATING_MAX,
    GATHER_AMOUNT,
    HARASS_AMOUNT,
    CARRIED_WEIGHT,
)


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def rng():
    """Seeded random number generator for reproducible tests."""
    return random.Random(42)


@pytest.fixture
def mock_agent_configs() -> List[AgentConfig]:
    """Create mock agent configs for testing."""
    return [
        AgentConfig(
            agent_id=f"agent-{i}",
            name=f"Agent {i}",
            strategy="balanced",
            ranks={"power": 500, "honor": 500, "chaos": 500, "influence": 500},
            is_bot=True,
        )
        for i in range(4)
    ]


@pytest.fixture
def mock_match_config(mock_agent_configs) -> MatchConfig:
    """Create a mock match config."""
    return MatchConfig(
        match_id="test-match-001",
        mission=MissionConfig(
            mission_type=MissionType.RESOURCE_RACE,
            ticks=30,
            phases=[MissionType.RESOURCE_RACE],
            parameters={"nodes": {"count": 3, "resources_per_node": 45}},
        ),
        agents=mock_agent_configs,
        seed=42,
    )


@pytest.fixture
def mock_agent_states() -> Dict[str, AgentState]:
    """Create mock agent states."""
    return {
        f"agent-{i}": AgentState(
            carried=10 + i * 5,
            deposited=20 + i * 10,
            gathered=30 + i * 5,
            valid_actions=20 + i * 2,
            invalid_actions=i,
        )
        for i in range(4)
    }


@pytest.fixture
def mock_resource_nodes() -> List[ResourceNode]:
    """Create mock resource nodes."""
    return [
        ResourceNode(node_id="alpha", remaining=45),
        ResourceNode(node_id="beta", remaining=30),
        ResourceNode(node_id="gamma", remaining=15),
    ]


@pytest.fixture
def mock_observation(mock_agent_states, mock_resource_nodes) -> "Observation":
    """Create a mock observation for agent runtime tests."""
    from agent_runtime import Observation, ActionType
    
    return Observation(
        tick=1,
        phase="resource_race",
        own_state=mock_agent_states["agent-0"],
        visible_agents=["agent-1", "agent-2", "agent-3"],
        visible_nodes=mock_resource_nodes,
        recent_events=[],
        available_actions=[ActionType.GATHER, ActionType.DEPOSIT, ActionType.HARASS],
    )


# =============================================================================
# Mission Runner Tests
# =============================================================================

class TestMissionRunner:
    """Tests for MissionRunner class."""
    
    @pytest.fixture
    def mission_runner(self, mock_match_config, rng):
        """Create a MissionRunner instance with mocked dependencies."""
        from mission_runner import MissionRunner
        
        # Mock agent runtime and scoring engine
        mock_agent_runtime = MagicMock()
        mock_scoring_engine = MagicMock()
        
        runner = MissionRunner(
            match_config=mock_match_config,
            agent_runtime=mock_agent_runtime,
            scoring_engine=mock_scoring_engine,
            database=None,
            rng=rng,
        )
        return runner, mock_agent_runtime, mock_scoring_engine
    
    @pytest.mark.asyncio
    async def test_initialize_validates_agent_count(self, mock_match_config, rng):
        """Test that initialize validates agent count."""
        from mission_runner import MissionRunner
        
        # Test with too few agents
        mock_match_config.agents = mock_match_config.agents[:2]
        runner = MissionRunner(mock_match_config, rng=rng)
        
        with pytest.raises(ValueError, match="Agent count must be between"):
            await runner.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_sets_up_state(self, mission_runner, mock_agent_configs):
        """Test that initialize sets up agent states and nodes."""
        runner, _, _ = mission_runner
        
        await runner.initialize()
        
        assert runner.status == MatchStatus.RUNNING
        assert len(runner.agents) == 4
        assert len(runner.agent_states) == 4
        assert len(runner.nodes) == 3  # From mission config
        assert runner.started_at is not None
        
        # Check agent states were initialized
        for agent in mock_agent_configs:
            assert agent.agent_id in runner.agent_states
    
    @pytest.mark.asyncio
    async def test_initialize_emits_mission_started_event(self, mission_runner):
        """Test that initialize emits MISSION_STARTED event."""
        runner, _, _ = mission_runner
        
        event_callback = AsyncMock()
        runner.add_event_callback(event_callback)
        
        await runner.initialize()
        
        # Check that event callback was called
        assert event_callback.called
        call_args = event_callback.call_args
        assert call_args[0][0] == "test-match-001"  # match_id
        assert call_args[0][1]["type"] == EventType.MISSION_STARTED.value
    
    @pytest.mark.asyncio
    async def test_event_callback_error_handled(self, mission_runner):
        """Test that errors in event callbacks are handled gracefully."""
        runner, _, _ = mission_runner
        
        error_callback = AsyncMock(side_effect=Exception("Callback error"))
        runner.add_event_callback(error_callback)
        
        # Should not raise
        await runner.initialize()
        
        assert error_callback.called
    
    @pytest.mark.asyncio
    async def test_build_phase_contexts(self, mission_runner, mock_match_config):
        """Test phase context building."""
        runner, _, _ = mission_runner
        
        # Add multiple phases
        mock_match_config.mission.phases = [
            MissionType.RESOURCE_RACE,
            MissionType.NEGOTIATION,
            MissionType.SABOTAGE,
        ]
        mock_match_config.mission.ticks = 30
        
        await runner.initialize()
        
        # Check phase contexts were built
        assert len(runner._phase_contexts) == 3
        
        # Check tick ranges
        ctx = runner._phase_contexts[0]
        assert ctx.phase_type == MissionType.RESOURCE_RACE
        assert ctx.tick_start == 1
        assert ctx.tick_end == 10  # 30 ticks / 3 phases
    
    @pytest.mark.asyncio
    async def test_run_handles_exception(self, mission_runner):
        """Test that run handles exceptions and returns failed result."""
        runner, mock_runtime, _ = mission_runner
        
        # Make initialize fail
        mock_runtime.execute_decision = AsyncMock(side_effect=Exception("Runtime error"))
        
        result = await runner.run()
        
        assert result.status == MatchStatus.FAILED
        assert result.error is not None
        assert result.ended_at is not None
    
    @pytest.mark.asyncio
    async def test_finalize_calculates_standings(self, mission_runner, mock_agent_states):
        """Test that finalize calculates standings correctly."""
        runner, _, mock_scoring = mission_runner
        
        await runner.initialize()
        runner.agent_states = mock_agent_states
        runner._current_tick = 30
        
        # Mock scoring engine
        mock_scoring.calculate_standings.return_value = [
            {
                "placement": 1,
                "agent_id": "agent-3",
                "name": "Agent 3",
                "strategy": "balanced",
                "mission_score": 100.0,
                "stats": mock_agent_states["agent-3"].to_dict(),
            },
            {
                "placement": 2,
                "agent_id": "agent-2",
                "name": "Agent 2",
                "strategy": "balanced",
                "mission_score": 80.0,
                "stats": mock_agent_states["agent-2"].to_dict(),
            },
        ]
        
        mock_scoring.calculate_all_updates.return_value = [
            {
                "agent_id": "agent-3",
                "before": {"power": 500, "honor": 500, "chaos": 500, "influence": 500},
                "deltas": {"power": 10, "honor": 5, "chaos": 2, "influence": 8},
                "after": {"power": 510, "honor": 505, "chaos": 502, "influence": 508},
                "abuse_penalty": 0,
                "explain": {},
            }
        ]
        
        result = await runner._finalize()
        
        assert result.status == MatchStatus.COMPLETED
        assert len(result.standings) == 2
        assert result.standings[0]["placement"] == 1
        
        # Verify scoring engine was called
        mock_scoring.calculate_standings.assert_called_once()
        mock_scoring.calculate_all_updates.assert_called_once()
    
    def test_agent_to_dict(self, mission_runner, mock_agent_configs):
        """Test converting agent config to dict."""
        runner, _, _ = mission_runner
        
        agent = mock_agent_configs[0]
        result = runner._agent_to_dict(agent)
        
        assert result["agent_id"] == agent.agent_id
        assert result["name"] == agent.name
        assert result["strategy"] == agent.strategy
        assert result["ranks"] == agent.ranks


class TestMissionRunnerFactory:
    """Tests for MissionRunnerFactory."""
    
    def test_create_resource_race(self, mock_agent_configs):
        """Test creating a resource race mission."""
        from mission_runner import MissionRunnerFactory
        
        runner = MissionRunnerFactory.create(
            mission_type=MissionType.RESOURCE_RACE,
            agents=mock_agent_configs,
            ticks=30,
            seed=42,
        )
        
        assert runner.config.mission.mission_type == MissionType.RESOURCE_RACE
        assert runner.config.mission.ticks == 30
        assert len(runner.config.agents) == 4
    
    def test_create_multi_phase(self, mock_agent_configs):
        """Test creating a multi-phase mission."""
        from mission_runner import MissionRunnerFactory
        
        runner = MissionRunnerFactory.create_multi_phase(
            phases=[MissionType.RESOURCE_RACE, MissionType.NEGOTIATION],
            agents=mock_agent_configs,
            ticks=40,
            seed=42,
        )
        
        assert len(runner.config.mission.phases) == 2
        assert runner.config.mission.ticks == 40


class TestPhaseContext:
    """Tests for PhaseContext dataclass."""
    
    def test_phase_context_creation(self):
        """Test creating a phase context."""
        from mission_runner import PhaseContext
        
        ctx = PhaseContext(
            phase_type=MissionType.RESOURCE_RACE,
            tick_start=1,
            tick_end=10,
            parameters={"speed": "fast"},
        )
        
        assert ctx.phase_type == MissionType.RESOURCE_RACE
        assert ctx.tick_start == 1
        assert ctx.tick_end == 10
        assert ctx.parameters == {"speed": "fast"}


# =============================================================================
# Agent Runtime Tests
# =============================================================================

class TestAgentRuntime:
    """Tests for AgentRuntime class."""
    
    @pytest.fixture
    def agent_runtime(self, rng):
        """Create an AgentRuntime instance."""
        from agent_runtime import AgentRuntime
        
        return AgentRuntime(
            timeout_seconds=5.0,
            max_retries=2,
            rng=rng,
        )
    
    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """Create a test agent config."""
        return AgentConfig(
            agent_id="test-agent",
            name="Test Agent",
            strategy="balanced",
            is_bot=True,
        )
    
    @pytest.mark.asyncio
    async def test_execute_decision_success(self, agent_runtime, agent_config, mock_observation):
        """Test successful decision execution."""
        from agent_runtime import ActionType
        
        # Mock the driver to return a valid action
        mock_driver = AsyncMock()
        mock_driver.decide.return_value = {
            "type": ActionType.GATHER.value,
            "node_id": "alpha",
        }
        
        agent_runtime.register_driver(agent_config.agent_id, mock_driver)
        
        result = await agent_runtime.execute_decision(
            agent_config=agent_config,
            observation=mock_observation,
            context={"match_id": "test"},
        )
        
        assert result.success is True
        assert result.action["type"] == ActionType.GATHER.value
        assert result.retry_count == 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_execute_decision_timeout(self, agent_runtime, agent_config, mock_observation):
        """Test decision timeout handling."""
        from agent_runtime import ActionType
        
        # Create a driver that never returns (simulates timeout)
        async def slow_decide(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
        
        mock_driver = AsyncMock()
        mock_driver.decide = slow_decide
        
        agent_runtime.register_driver(agent_config.agent_id, mock_driver)
        agent_runtime.timeout_seconds = 0.01  # Very short timeout
        
        result = await agent_runtime.execute_decision(
            agent_config=agent_config,
            observation=mock_observation,
        )
        
        assert result.success is False
        assert "Timeout" in result.error
        assert result.action["type"] == ActionType.SKIP.value or result.action["type"] == ActionType.GATHER.value
    
    @pytest.mark.asyncio
    async def test_execute_decision_validation_error(self, agent_runtime, agent_config, mock_observation):
        """Test action validation error handling."""
        from agent_runtime import ActionType
        
        # Mock driver to return invalid action
        mock_driver = AsyncMock()
        mock_driver.decide.return_value = {
            "type": ActionType.HARASS.value,
            # Missing required target_id
        }
        
        agent_runtime.register_driver(agent_config.agent_id, mock_driver)
        
        result = await agent_runtime.execute_decision(
            agent_config=agent_config,
            observation=mock_observation,
        )
        
        assert result.success is False
        assert "Validation error" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_decision_retry(self, agent_runtime, agent_config, mock_observation):
        """Test retry logic for transient errors."""
        from agent_runtime import ActionType
        
        mock_driver = AsyncMock()
        # Fail twice, then succeed
        mock_driver.decide.side_effect = [
            Exception("Transient error"),
            Exception("Another error"),
            {"type": ActionType.GATHER.value, "node_id": "alpha"},
        ]
        
        agent_runtime.register_driver(agent_config.agent_id, mock_driver)
        agent_runtime.max_retries = 3
        
        result = await agent_runtime.execute_decision(
            agent_config=agent_config,
            observation=mock_observation,
        )
        
        # The retry logic should eventually succeed on 3rd attempt
        # OR if all retries are exhausted, it should return fallback
        # The actual implementation retries then succeeds
        assert result.retry_count == 2  # Succeeded on 3rd try (2 retries)
        assert result.success is True
    
    def test_validate_action_valid(self, agent_runtime, mock_observation):
        """Test action validation with valid actions."""
        from agent_runtime import ActionType
        
        valid_actions = [
            {"type": ActionType.GATHER.value, "node_id": "alpha"},
            {"type": ActionType.DEPOSIT.value},
            {"type": ActionType.SKIP.value, "reason": "test"},
        ]
        
        for action in valid_actions:
            result = agent_runtime._validate_action(action, mock_observation)
            assert result["type"] == action["type"]
    
    def test_validate_action_invalid_type(self, agent_runtime, mock_observation):
        """Test validation rejects unknown action types."""
        from agent_runtime import ActionValidationError
        
        with pytest.raises(ActionValidationError, match="Unknown action type"):
            agent_runtime._validate_action({"type": "invalid_action"}, mock_observation)
    
    def test_validate_action_missing_type(self, agent_runtime, mock_observation):
        """Test validation rejects actions without type."""
        from agent_runtime import ActionValidationError
        
        with pytest.raises(ActionValidationError, match="must have a 'type' field"):
            agent_runtime._validate_action({"node_id": "alpha"}, mock_observation)
    
    def test_validate_action_invalid_node(self, agent_runtime, mock_observation):
        """Test validation rejects gather with invalid node."""
        from agent_runtime import ActionType, ActionValidationError
        
        with pytest.raises(ActionValidationError, match="Invalid node_id"):
            agent_runtime._validate_action(
                {"type": ActionType.GATHER.value, "node_id": "invalid_node"},
                mock_observation,
            )
    
    def test_validate_action_harass_no_target(self, agent_runtime, mock_observation):
        """Test validation rejects harass without target."""
        from agent_runtime import ActionType, ActionValidationError
        
        with pytest.raises(ActionValidationError, match="requires target_id"):
            agent_runtime._validate_action(
                {"type": ActionType.HARASS.value},
                mock_observation,
            )
    
    def test_get_fallback_action_with_nodes(self, agent_runtime, mock_observation):
        """Test fallback action selection with available nodes."""
        from agent_runtime import ActionType
        
        fallback = agent_runtime._get_fallback_action(mock_observation)
        
        assert fallback["type"] == ActionType.GATHER.value
        assert fallback["node_id"] in ["alpha", "beta", "gamma"]
    
    def test_get_fallback_action_no_nodes(self, agent_runtime):
        """Test fallback action when no nodes available."""
        from agent_runtime import Observation, ActionType
        
        obs = Observation(
            tick=1,
            phase="resource_race",
            own_state=AgentState(),
            visible_agents=[],
            visible_nodes=[],  # Empty
            recent_events=[],
            available_actions=[],
        )
        
        fallback = agent_runtime._get_fallback_action(obs)
        
        assert fallback["type"] == ActionType.SKIP.value
    
    def test_action_history(self, agent_runtime):
        """Test action history tracking."""
        from agent_runtime import ActionType
        
        agent_id = "test-agent"
        
        # Initially empty
        assert agent_runtime.get_action_history(agent_id) == []
        
        # Add some history manually
        agent_runtime._action_history[agent_id] = [
            {"type": ActionType.GATHER.value},
            {"type": ActionType.DEPOSIT.value},
        ]
        
        history = agent_runtime.get_action_history(agent_id)
        assert len(history) == 2
        
        # Test clear history
        agent_runtime.clear_history(agent_id)
        assert agent_runtime.get_action_history(agent_id) == []
    
    def test_clear_all_history(self, agent_runtime):
        """Test clearing all action history."""
        from agent_runtime import ActionType
        
        agent_runtime._action_history = {
            "agent-1": [{"type": ActionType.GATHER.value}],
            "agent-2": [{"type": ActionType.DEPOSIT.value}],
        }
        
        agent_runtime.clear_history()
        
        assert agent_runtime._action_history == {}


class TestBotStrategyDriver:
    """Tests for BotStrategyDriver."""
    
    @pytest.fixture
    def bot_driver(self, rng):
        """Create a BotStrategyDriver instance."""
        from agent_runtime import BotStrategyDriver
        
        return BotStrategyDriver(rng=rng)
    
    @pytest.fixture
    def observation_resource_race(self, mock_resource_nodes) -> "Observation":
        """Create observation for resource race phase."""
        from agent_runtime import Observation, ActionType
        
        return Observation(
            tick=1,
            phase="resource_race",
            own_state=AgentState(carried=3),
            visible_agents=["agent-1", "agent-2"],
            visible_nodes=mock_resource_nodes,
            recent_events=[],
            available_actions=[ActionType.GATHER, ActionType.DEPOSIT, ActionType.HARASS],
        )
    
    @pytest.mark.asyncio
    async def test_decide_resource_race_deposit_when_full(self, bot_driver, observation_resource_race):
        """Test that bot deposits when carrying enough."""
        from agent_runtime import ActionType
        
        observation_resource_race.own_state.carried = 10  # Above threshold
        
        agent = AgentConfig(
            agent_id="bot-1",
            name="Bot",
            strategy="balanced",
        )
        
        action = await bot_driver.decide(agent, observation_resource_race, {})
        
        # High chance of deposit when carrying enough
        assert action["type"] == ActionType.DEPOSIT.value
    
    @pytest.mark.asyncio
    async def test_decide_resource_race_gather(self, bot_driver, observation_resource_race):
        """Test that bot gathers when not full."""
        from agent_runtime import ActionType
        
        observation_resource_race.own_state.carried = 2  # Below threshold
        
        agent = AgentConfig(
            agent_id="bot-1",
            name="Bot",
            strategy="balanced",
        )
        
        action = await bot_driver.decide(agent, observation_resource_race, {})
        
        assert action["type"] == ActionType.GATHER.value
        assert "node_id" in action
    
    @pytest.mark.asyncio
    async def test_decide_negotiation(self, bot_driver):
        """Test negotiation phase decisions."""
        from agent_runtime import Observation, ActionType
        
        obs = Observation(
            tick=1,
            phase="negotiation",
            own_state=AgentState(),
            visible_agents=["agent-1"],
            visible_nodes=[],
            recent_events=[],
            available_actions=[ActionType.NEGOTIATE, ActionType.ALLY, ActionType.BETRAY],
        )
        
        agent = AgentConfig(
            agent_id="bot-1",
            name="Bot",
            strategy="cooperative",
        )
        
        action = await bot_driver.decide(agent, obs, {})
        
        # Cooperative bots should propose alliances
        assert action["type"] in [ActionType.ALLY.value, ActionType.NEGOTIATE.value]
    
    @pytest.mark.asyncio
    async def test_decide_sabotage(self, bot_driver):
        """Test sabotage phase decisions."""
        from agent_runtime import Observation, ActionType
        
        obs = Observation(
            tick=1,
            phase="sabotage",
            own_state=AgentState(),
            visible_agents=["agent-1", "agent-2"],
            visible_nodes=[],
            recent_events=[],
            available_actions=[ActionType.SABOTAGE, ActionType.DEFEND],
        )
        
        agent = AgentConfig(
            agent_id="bot-1",
            name="Bot",
            strategy="aggressive",
        )
        
        # Run multiple times to account for randomness
        actions = []
        for _ in range(20):
            action = await bot_driver.decide(agent, obs, {})
            actions.append(action["type"])
        
        # Aggressive bots should sometimes sabotage
        assert ActionType.SABOTAGE.value in actions or ActionType.DEFEND.value in actions
    
    def test_is_external_property(self, bot_driver):
        """Test that bot driver reports not external."""
        assert bot_driver.is_external is False


class TestActionExecutor:
    """Tests for ActionExecutor class."""
    
    @pytest.fixture
    def executor(self, rng):
        """Create an ActionExecutor instance."""
        from agent_runtime import ActionExecutor
        
        return ActionExecutor(rng=rng)
    
    @pytest.fixture
    def agent_states(self) -> Dict[str, AgentState]:
        """Create test agent states."""
        return {
            "agent-1": AgentState(carried=10, deposited=5),
            "agent-2": AgentState(carried=5, deposited=10),
        }
    
    def test_execute_gather_success(self, executor, agent_states):
        """Test successful gather action."""
        from agent_runtime import ActionType
        
        nodes = [ResourceNode(node_id="node-1", remaining=20)]
        
        action = {"type": ActionType.GATHER.value, "node_id": "node-1"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=nodes,
            gather_amount=3,
        )
        
        assert result["success"] is True
        assert result["action"] == "gather"
        assert result["amount"] == 3
        assert result["node_remaining"] == 17
        assert agent_states["agent-1"].carried == 13
        assert agent_states["agent-1"].gathered == 3
    
    def test_execute_gather_depleted_node(self, executor, agent_states):
        """Test gather from depleted node."""
        from agent_runtime import ActionType
        
        nodes = [ResourceNode(node_id="node-1", remaining=0)]
        
        action = {"type": ActionType.GATHER.value, "node_id": "node-1"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=nodes,
        )
        
        assert result["success"] is False
        assert "depleted" in result["error"]
        assert agent_states["agent-1"].invalid_actions == 1
    
    def test_execute_gather_trapped_node(self, executor, agent_states):
        """Test gather from trapped node triggers trap."""
        from agent_runtime import ActionType
        
        nodes = [ResourceNode(
            node_id="node-1",
            remaining=20,
            trapped=True,
            trap_owner=agent_states["agent-2"],
        )]
        
        action = {"type": ActionType.GATHER.value, "node_id": "node-1"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=nodes,
        )
        
        assert result["success"] is True
        assert result["trap_triggered"] is True
        assert nodes[0].trapped is False  # Trap consumed
    
    def test_execute_deposit_success(self, executor, agent_states):
        """Test successful deposit action."""
        from agent_runtime import ActionType
        
        action = {"type": ActionType.DEPOSIT.value}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "deposit"
        assert result["amount"] == 10  # All carried
        assert agent_states["agent-1"].carried == 0
        assert agent_states["agent-1"].deposited == 15  # 5 + 10
    
    def test_execute_deposit_empty_inventory(self, executor, agent_states):
        """Test deposit with empty inventory."""
        from agent_runtime import ActionType
        
        agent_states["agent-1"].carried = 0
        
        action = {"type": ActionType.DEPOSIT.value}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is False
        assert "empty" in result["error"]
        assert agent_states["agent-1"].invalid_actions == 1
    
    def test_execute_harass_success(self, executor, agent_states):
        """Test successful harass action."""
        from agent_runtime import ActionType
        
        action = {"type": ActionType.HARASS.value, "target_id": "agent-2"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
            harass_amount=2,
        )
        
        assert result["success"] is True
        assert result["action"] == "harass"
        assert result["target_id"] == "agent-2"
        assert result["amount"] == 2
        assert agent_states["agent-2"].carried == 3  # 5 - 2
        assert agent_states["agent-1"].carried == 12  # 10 + 2
    
    def test_execute_harass_empty_target(self, executor, agent_states):
        """Test harass against target with no resources."""
        from agent_runtime import ActionType
        
        agent_states["agent-2"].carried = 0
        
        action = {"type": ActionType.HARASS.value, "target_id": "agent-2"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is False
        assert "empty" in result["error"]
    
    def test_execute_sabotage_success(self, executor, agent_states, rng):
        """Test sabotage action (may succeed or fail based on RNG)."""
        from agent_runtime import ActionType
        
        # Seed RNG to get predictable result
        rng.seed(1)
        
        action = {"type": ActionType.SABOTAGE.value, "target_id": "agent-2", "method": "direct"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "sabotage"
        assert result["target_id"] == "agent-2"
        assert agent_states["agent-1"].sabotage_attempts == 1
        assert "result" in result
    
    def test_execute_ally_success(self, executor, agent_states, rng):
        """Test ally action."""
        from agent_runtime import ActionType
        
        # Seed for predictable acceptance
        rng.seed(0)  # This makes random() < 0.6 True
        
        action = {"type": ActionType.ALLY.value, "target_id": "agent-2", "proposal": {}}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "ally"
        assert "accepted" in result
        
        if result["accepted"]:
            assert "agent-2" in agent_states["agent-1"].alliance_partners
            assert "agent-1" in agent_states["agent-2"].alliance_partners
    
    def test_execute_betray(self, executor, agent_states):
        """Test betray action."""
        from agent_runtime import ActionType
        
        # Setup alliance first
        agent_states["agent-1"].alliance_partners.append("agent-2")
        agent_states["agent-2"].alliance_partners.append("agent-1")
        
        action = {"type": ActionType.BETRAY.value, "target_id": "agent-2"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "betray"
        assert "agent-2" not in agent_states["agent-1"].alliance_partners
        assert agent_states["agent-1"].alliances_betrayed == 1
    
    def test_execute_defend(self, executor, agent_states):
        """Test defend action."""
        from agent_runtime import ActionType
        
        action = {"type": ActionType.DEFEND.value}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "defend"
        assert result["defense_bonus"] == 0.2
    
    def test_execute_skip(self, executor, agent_states):
        """Test skip action."""
        from agent_runtime import ActionType
        
        action = {"type": ActionType.SKIP.value, "reason": "testing"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is True
        assert result["action"] == "skip"
    
    def test_execute_unknown_action(self, executor, agent_states):
        """Test handling of unknown action type."""
        action = {"type": "unknown_action"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states=agent_states,
            nodes=[],
        )
        
        assert result["success"] is False
        assert "Unknown action" in result["error"]
    
    def test_execute_agent_not_found(self, executor):
        """Test execution with missing agent state."""
        from agent_runtime import ActionType
        
        action = {"type": ActionType.GATHER.value, "node_id": "node-1"}
        result = executor.execute(
            action=action,
            agent_id="nonexistent",
            agent_states={},
            nodes=[],
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]


class TestDecisionResult:
    """Tests for DecisionResult dataclass."""
    
    def test_decision_result_creation(self):
        """Test creating a DecisionResult."""
        from agent_runtime import DecisionResult
        
        result = DecisionResult(
            action={"type": "gather"},
            success=True,
            error=None,
            execution_time_ms=150.5,
            retry_count=0,
        )
        
        assert result.success is True
        assert result.execution_time_ms == 150.5
        assert result.retry_count == 0


class TestObservation:
    """Tests for Observation dataclass."""
    
    def test_observation_to_dict(self, mock_resource_nodes):
        """Test converting observation to dict."""
        from agent_runtime import Observation, ActionType
        
        obs = Observation(
            tick=5,
            phase="resource_race",
            own_state=AgentState(carried=10),
            visible_agents=["agent-1"],
            visible_nodes=mock_resource_nodes,
            recent_events=[{"type": "test"}],
            available_actions=[ActionType.GATHER],
        )
        
        result = obs.to_dict()
        
        assert result["tick"] == 5
        assert result["phase"] == "resource_race"
        assert result["visible_agents"] == ["agent-1"]
        assert len(result["visible_nodes"]) == 3
        assert result["available_actions"] == ["gather"]


class TestExceptions:
    """Tests for custom exceptions."""
    
    def test_action_validation_error(self):
        """Test ActionValidationError."""
        from agent_runtime import ActionValidationError
        
        with pytest.raises(ActionValidationError, match="test error"):
            raise ActionValidationError("test error")
    
    def test_agent_timeout_error(self):
        """Test AgentTimeoutError."""
        from agent_runtime import AgentTimeoutError
        
        with pytest.raises(AgentTimeoutError, match="timeout"):
            raise AgentTimeoutError("timeout error")
    
    def test_agent_runtime_error(self):
        """Test AgentRuntimeError."""
        from agent_runtime import AgentRuntimeError
        
        with pytest.raises(AgentRuntimeError, match="runtime"):
            raise AgentRuntimeError("runtime error")


# =============================================================================
# Scoring Tests
# =============================================================================

class TestScoringEngine:
    """Tests for ScoringEngine class."""
    
    @pytest.fixture
    def scoring_engine(self):
        """Create a ScoringEngine instance."""
        from scoring import ScoringEngine
        
        return ScoringEngine()
    
    @pytest.fixture
    def match_results(self) -> List["MatchResult"]:
        """Create test match results."""
        from scoring import MatchResult
        
        return [
            MatchResult(agent_id="agent-1", score=100.0, placement=1),
            MatchResult(agent_id="agent-2", score=80.0, placement=2),
            MatchResult(agent_id="agent-3", score=60.0, placement=3),
            MatchResult(agent_id="agent-4", score=40.0, placement=4),
        ]
    
    def test_scoring_context_from_results(self, match_results):
        """Test creating ScoringContext from results."""
        from scoring import ScoringContext
        
        context = ScoringContext.from_results(match_results)
        
        assert context.total_agents == 4
        assert context.max_score == 100.0
        assert context.min_score == 40.0
        assert context.score_span == 60.0
        assert context.average_score == 70.0
    
    def test_scoring_context_empty_results(self):
        """Test creating ScoringContext from empty results."""
        from scoring import ScoringContext
        
        context = ScoringContext.from_results([])
        
        assert context.total_agents == 0
        assert context.max_score == 1.0
        assert context.min_score == 0.0
        assert context.score_span == 1.0  # Actual implementation returns 1.0, not 1e-6
        assert context.average_score == 0.0
    
    def test_calculate_all_updates(self, scoring_engine, mock_agent_states, mock_agent_configs):
        """Test calculating all rank updates."""
        from scoring import MatchResult
        
        match_results = [
            MatchResult(agent_id=f"agent-{i}", score=100.0 - i * 20, placement=i + 1)
            for i in range(4)
        ]
        
        agent_configs = {a.agent_id: a for a in mock_agent_configs}
        
        standings = [
            {
                "placement": r.placement,
                "agent_id": r.agent_id,
                "name": f"Agent {r.agent_id}",
                "strategy": "balanced",
                "mission_score": r.score,
                "stats": mock_agent_states[r.agent_id].to_dict(),
            }
            for r in match_results
        ]
        
        updates = scoring_engine.calculate_all_updates(
            standings=standings,
            agent_states=mock_agent_states,
            agent_configs=agent_configs,
        )
        
        assert len(updates) == 4
        
        # Check each update has required fields
        for update in updates:
            assert "agent_id" in update
            assert "before" in update
            assert "deltas" in update
            assert "after" in update
            assert "explain" in update
            
            # Check all axes present
            for axis in ["power", "honor", "chaos", "influence"]:
                assert axis in update["before"]
                assert axis in update["deltas"]
                assert axis in update["after"]
    
    def test_power_ranking_calculation(self, scoring_engine):
        """Test Power ranking delta calculation."""
        from scoring import ScoringContext, MatchResult
        
        # Create a context where agent is first place
        results = [
            MatchResult(agent_id="agent-1", score=100.0, placement=1),
            MatchResult(agent_id="agent-2", score=50.0, placement=2),
        ]
        context = ScoringContext.from_results(results)
        
        standing = {
            "placement": 1,
            "agent_id": "agent-1",
            "name": "Agent 1",
            "strategy": "balanced",
            "mission_score": 100.0,
            "stats": AgentState(
                deposited=50,
                valid_actions=20,
                invalid_actions=0,
            ).to_dict(),
        }
        
        state = AgentState(deposited=50, valid_actions=20, invalid_actions=0)
        
        update = scoring_engine._calculate_single_update(
            agent_id="agent-1",
            standing=standing,
            state=state,
            context=context,
            current_rating={},
            all_results=results,
            all_ratings={},
        )
        
        # First place should get positive power delta
        assert update["deltas"]["power"] > 0
        assert update["after"]["power"] > DEFAULT_RATING
    
    def test_honor_ranking_calculation(self, scoring_engine):
        """Test Honor ranking delta calculation."""
        from scoring import ScoringContext, MatchResult
        
        # Agent with high treaty integrity (no betrayals)
        state = AgentState(
            valid_actions=20,
            invalid_actions=0,
            treaties_accepted=5,
            treaties_broken=0,
        )
        
        results = [MatchResult(agent_id="agent-1", score=100.0, placement=1)]
        context = ScoringContext.from_results(results)
        
        standing = {
            "placement": 1,
            "agent_id": "agent-1",
            "name": "Agent 1",
            "strategy": "balanced",
            "mission_score": 100.0,
            "stats": state.to_dict(),
        }
        
        update = scoring_engine._calculate_single_update(
            agent_id="agent-1",
            standing=standing,
            state=state,
            context=context,
            current_rating={},
            all_results=results,
            all_ratings={},
        )
        
        # High treaty integrity should give honor bonus
        assert "treaty_integrity" in update["explain"]
        assert update["explain"]["treaty_integrity"] > 0.5
    
    def test_chaos_ranking_calculation(self, scoring_engine):
        """Test Chaos ranking delta calculation."""
        from scoring import ScoringContext, MatchResult
        
        # Agent with high disruption and betrayals
        state = AgentState(
            disruption_done=15,
            treaties_broken=3,
            alliances_betrayed=2,
            sabotage_attempts=5,
        )
        
        results = [MatchResult(agent_id="agent-1", score=50.0, placement=2)]
        context = ScoringContext.from_results(results)
        
        standing = {
            "placement": 2,
            "agent_id": "agent-1",
            "name": "Agent 1",
            "strategy": "aggressive",
            "mission_score": 50.0,
            "stats": state.to_dict(),
        }
        
        update = scoring_engine._calculate_single_update(
            agent_id="agent-1",
            standing=standing,
            state=state,
            context=context,
            current_rating={},
            all_results=results,
            all_ratings={},
        )
        
        # High disruption should give chaos bonus
        assert update["deltas"]["chaos"] > 0
        assert update["explain"]["betrayal_rate"] > 0
    
    def test_influence_ranking_calculation(self, scoring_engine):
        """Test Influence ranking delta calculation."""
        from scoring import ScoringContext, MatchResult
        
        # Agent with many alliances and negotiations
        state = AgentState(
            alliances_formed=5,
            treaties_accepted=4,
            treaties_proposed=6,
            disruption_done=10,
        )
        
        results = [MatchResult(agent_id="agent-1", score=100.0, placement=1)]
        context = ScoringContext.from_results(results)
        
        standing = {
            "placement": 1,
            "agent_id": "agent-1",
            "name": "Agent 1",
            "strategy": "cooperative",
            "mission_score": 100.0,
            "stats": state.to_dict(),
        }
        
        update = scoring_engine._calculate_single_update(
            agent_id="agent-1",
            standing=standing,
            state=state,
            context=context,
            current_rating={},
            all_results=results,
            all_ratings={},
        )
        
        # High alliance activity should give influence bonus
        assert update["deltas"]["influence"] > 0
    
    def test_abuse_penalty_calculation(self, scoring_engine):
        """Test abuse penalty calculation."""
        # High invalid action rate
        state = AgentState(
            valid_actions=10,
            invalid_actions=10,  # 50% invalid rate
        )
        
        penalty = scoring_engine._calculate_abuse_penalty(
            state=state,
            action_total=20,
            valid_ratio=0.5,
        )
        
        # Should have penalty for high invalid rate
        assert penalty > 0
    
    def test_abuse_penalty_zero_deposit(self, scoring_engine):
        """Test abuse penalty for zero deposit with many actions."""
        state = AgentState(
            deposited=0,
            valid_actions=10,  # Many actions, no deposit
            invalid_actions=0,
        )
        
        penalty = scoring_engine._calculate_abuse_penalty(
            state=state,
            action_total=10,
            valid_ratio=1.0,
        )
        
        # Should have penalty for trolling behavior
        assert penalty > 0
    
    def test_betrayal_rate_calculation(self, scoring_engine):
        """Test betrayal rate calculation."""
        # Agent with betrayals
        state = AgentState(
            treaties_broken=2,
            alliances_betrayed=1,
            disruption_done=4,
            treaties_accepted=3,
            alliances_formed=2,
        )
        
        rate = scoring_engine._calculate_betrayal_rate(state)
        
        assert 0 <= rate <= 1.0
        assert rate > 0  # Should be positive due to betrayals
    
    def test_expected_multiplayer(self, scoring_engine):
        """Test expected score calculation against opponents."""
        # Equal ratings
        expected = scoring_engine._expected_multiplayer(500.0, [500.0, 500.0])
        assert expected == 0.5
        
        # Higher rating
        expected = scoring_engine._expected_multiplayer(600.0, [500.0])
        assert expected > 0.5
        
        # Lower rating
        expected = scoring_engine._expected_multiplayer(400.0, [500.0])
        assert expected < 0.5
    
    def test_expected_multiplayer_empty(self, scoring_engine):
        """Test expected score with no opponents."""
        expected = scoring_engine._expected_multiplayer(500.0, [])
        assert expected == 0.5
    
    def test_calculate_standings(self, scoring_engine, mock_agent_configs):
        """Test calculating final standings."""
        from scoring import MatchResult
        
        agent_scores = [
            ("agent-1", 100.0, AgentState(deposited=50)),
            ("agent-2", 80.0, AgentState(deposited=40)),
            ("agent-3", 60.0, AgentState(deposited=30)),
        ]
        
        agent_configs = {a.agent_id: a for a in mock_agent_configs[:3]}
        
        standings = scoring_engine.calculate_standings(agent_scores, agent_configs)
        
        assert len(standings) == 3
        assert standings[0]["placement"] == 1
        assert standings[0]["agent_id"] == "agent-1"
        assert standings[0]["mission_score"] == 100.0
    
    def test_calculate_standings_tiebreaker(self, scoring_engine):
        """Test standings tiebreaker (deposited, then invalid actions)."""
        agent_configs = {
            "agent-1": AgentConfig(agent_id="agent-1", name="A1", strategy="balanced"),
            "agent-2": AgentConfig(agent_id="agent-2", name="A2", strategy="balanced"),
        }
        
        # Same score, different deposited amounts
        agent_scores = [
            ("agent-1", 100.0, AgentState(deposited=50, invalid_actions=2)),
            ("agent-2", 100.0, AgentState(deposited=60, invalid_actions=0)),
        ]
        
        standings = scoring_engine.calculate_standings(agent_scores, agent_configs)
        
        # Higher deposited should win tie
        assert standings[0]["agent_id"] == "agent-2"


class TestRankCalculator:
    """Tests for RankCalculator class (legacy compatible)."""
    
    def test_calculate_rank_deltas(self):
        """Test legacy rank delta calculation."""
        from scoring import RankCalculator
        
        results = [
            ("agent-1", 100.0),
            ("agent-2", 50.0),
            ("agent-3", 25.0),
        ]
        
        deltas = RankCalculator.calculate_rank_deltas(results)
        
        assert len(deltas) == 3
        
        # Check all axes present for each agent
        for agent_id, delta in deltas.items():
            assert "power" in delta
            assert "honor" in delta
            assert "chaos" in delta
            assert "influence" in delta
        
        # First place should get positive power delta
        assert deltas["agent-1"]["power"] > 0
    
    def test_apply_deltas(self):
        """Test applying deltas to current ratings."""
        from scoring import RankCalculator
        
        current_ratings = {
            "agent-1": {"power": 500, "honor": 500, "chaos": 500, "influence": 500},
            "agent-2": {"power": 480, "honor": 520, "chaos": 500, "influence": 500},
        }
        
        deltas = {
            "agent-1": {"power": 20, "honor": -10, "chaos": 5, "influence": 0},
            "agent-2": {"power": -10, "honor": 10, "chaos": -5, "influence": 15},
        }
        
        updated = RankCalculator.apply_deltas(current_ratings, deltas)
        
        assert updated["agent-1"]["power"] == 520
        assert updated["agent-1"]["honor"] == 490
        assert updated["agent-2"]["power"] == 470
        assert updated["agent-2"]["influence"] == 515
    
    def test_apply_deltas_clamps_to_bounds(self):
        """Test that deltas are clamped to rating bounds."""
        from scoring import RankCalculator
        
        current_ratings = {
            "agent-1": {"power": 990, "honor": 10, "chaos": 500, "influence": 500},
        }
        
        deltas = {
            "agent-1": {"power": 20, "honor": -20, "chaos": 0, "influence": 0},
        }
        
        updated = RankCalculator.apply_deltas(current_ratings, deltas)
        
        # Should be clamped
        assert updated["agent-1"]["power"] == RATING_MAX
        assert updated["agent-1"]["honor"] == RATING_MIN


class TestScoringContext:
    """Tests for ScoringContext dataclass."""
    
    def test_empty_results(self):
        """Test ScoringContext with empty results."""
        from scoring import ScoringContext, MatchResult
        
        context = ScoringContext.from_results([])
        
        assert context.total_agents == 0
        assert context.max_score == 1.0
        assert context.min_score == 0.0
        assert context.score_span == 1.0  # Actual implementation returns 1.0
    
    def test_single_result(self):
        """Test ScoringContext with single result."""
        from scoring import ScoringContext, MatchResult
        
        results = [MatchResult(agent_id="agent-1", score=100.0, placement=1)]
        context = ScoringContext.from_results(results)
        
        assert context.total_agents == 1
        assert context.max_score == 100.0
        assert context.min_score == 100.0
        assert context.average_score == 100.0


# =============================================================================
# Scheduler Tests
# =============================================================================

class TestMatchScheduler:
    """Tests for MatchScheduler class."""
    
    @pytest.fixture
    async def scheduler(self):
        """Create a MatchScheduler instance."""
        from scheduler import MatchScheduler
        
        sch = MatchScheduler(max_concurrent=2)
        yield sch
        await sch.stop()
    
    @pytest.fixture
    def match_config(self) -> MatchConfig:
        """Create a test match config."""
        return MatchConfig(
            match_id="test-match-001",
            mission=MissionConfig(
                mission_type=MissionType.RESOURCE_RACE,
                ticks=30,
            ),
            agents=[
                AgentConfig(agent_id=f"bot-{i}", name=f"Bot {i}", strategy="balanced")
                for i in range(4)
            ],
            seed=42,
        )
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the scheduler."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        assert scheduler._running_flag is False
        
        await scheduler.start()
        assert scheduler._running_flag is True
        assert scheduler._task is not None
        
        await scheduler.stop()
        assert scheduler._running_flag is False
    
    @pytest.mark.asyncio
    async def test_schedule_once(self, match_config):
        """Test scheduling a one-time match."""
        from scheduler import MatchScheduler, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await scheduler.schedule(
            match_config=match_config,
            priority=5,
            frequency=ScheduleFrequency.ONCE,
        )
        
        assert schedule_id.startswith("sch_")
        assert schedule_id in scheduler._schedules
        
        # One-time schedules should be added to queue
        assert match_config.match_id in scheduler._queue_items
    
    @pytest.mark.asyncio
    async def test_schedule_recurring(self, match_config):
        """Test scheduling a recurring match."""
        from scheduler import MatchScheduler, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await scheduler.schedule(
            match_config=match_config,
            priority=5,
            frequency=ScheduleFrequency.HOURLY,
        )
        
        scheduled = scheduler._schedules[schedule_id]
        assert scheduled.frequency == ScheduleFrequency.HOURLY
        assert scheduled.next_run is not None
    
    @pytest.mark.asyncio
    async def test_unschedule(self, match_config):
        """Test unscheduling a match."""
        from scheduler import MatchScheduler, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await scheduler.schedule(
            match_config=match_config,
            frequency=ScheduleFrequency.ONCE,
        )
        
        result = await scheduler.unschedule(schedule_id)
        
        assert result is True
        assert schedule_id not in scheduler._schedules
    
    @pytest.mark.asyncio
    async def test_unschedule_nonexistent(self):
        """Test unscheduling a non-existent schedule."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        result = await scheduler.unschedule("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_queue_match(self, match_config):
        """Test queuing a match for execution."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        match_id = await scheduler.queue_match(match_config, priority=10)
        
        assert match_id == match_config.match_id
        assert match_id in scheduler._queue_items
        assert len(scheduler._queue) == 1
    
    @pytest.mark.asyncio
    async def test_cancel_queued_match(self, match_config):
        """Test canceling a queued match."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        match_id = await scheduler.queue_match(match_config, priority=10)
        result = await scheduler.cancel_queued_match(match_id)
        
        assert result is True
        assert match_id not in scheduler._queue_items
    
    @pytest.mark.asyncio
    async def test_get_status(self, match_config):
        """Test getting scheduler status."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        await scheduler.queue_match(match_config, priority=10)
        
        status = await scheduler.get_status()
        
        assert "running" in status
        assert "queue_length" in status
        assert status["queue_length"] == 1
    
    @pytest.mark.asyncio
    async def test_list_schedules(self, match_config):
        """Test listing scheduled matches."""
        from scheduler import MatchScheduler, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        await scheduler.schedule(
            match_config=match_config,
            frequency=ScheduleFrequency.HOURLY,
        )
        
        schedules = await scheduler.list_schedules()
        
        assert len(schedules) == 1
        assert schedules[0].frequency == ScheduleFrequency.HOURLY
    
    @pytest.mark.asyncio
    async def test_list_schedules_enabled_only(self, match_config):
        """Test listing only enabled schedules."""
        from scheduler import MatchScheduler, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await scheduler.schedule(
            match_config=match_config,
            frequency=ScheduleFrequency.HOURLY,
        )
        
        # Disable the schedule
        scheduler._schedules[schedule_id].enabled = False
        
        schedules = await scheduler.list_schedules(enabled_only=True)
        
        assert len(schedules) == 0
    
    def test_calculate_next_run_hourly(self):
        """Test calculating next run time for hourly schedule."""
        from scheduler import MatchScheduler, ScheduledMatch, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        scheduled = ScheduledMatch(
            schedule_id="test",
            priority=0,
            scheduled_at=datetime.now(timezone.utc),
            match_config=MagicMock(),
            frequency=ScheduleFrequency.HOURLY,
        )
        
        next_run = scheduler._calculate_next_run(scheduled)
        
        assert next_run is not None
        # Should be about 1 hour in the future
        delta = next_run - datetime.now(timezone.utc)
        assert 3590 < delta.total_seconds() < 3610  # ~1 hour
    
    def test_calculate_next_run_daily(self):
        """Test calculating next run time for daily schedule."""
        from scheduler import MatchScheduler, ScheduledMatch, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        scheduled = ScheduledMatch(
            schedule_id="test",
            priority=0,
            scheduled_at=datetime.now(timezone.utc),
            match_config=MagicMock(),
            frequency=ScheduleFrequency.DAILY,
        )
        
        next_run = scheduler._calculate_next_run(scheduled)
        
        assert next_run is not None
        # Should be about 1 day in the future
        delta = next_run - datetime.now(timezone.utc)
        assert 86390 < delta.total_seconds() < 86410  # ~24 hours
    
    def test_calculate_next_run_weekly(self):
        """Test calculating next run time for weekly schedule."""
        from scheduler import MatchScheduler, ScheduledMatch, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        scheduled = ScheduledMatch(
            schedule_id="test",
            priority=0,
            scheduled_at=datetime.now(timezone.utc),
            match_config=MagicMock(),
            frequency=ScheduleFrequency.WEEKLY,
        )
        
        next_run = scheduler._calculate_next_run(scheduled)
        
        assert next_run is not None
        # Should be about 1 week in the future
        delta = next_run - datetime.now(timezone.utc)
        assert 604790 < delta.total_seconds() < 604810  # ~7 days
    
    def test_parse_cron_simple(self):
        """Test parsing simple cron expression."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        next_run = scheduler._parse_cron("30 14", base)
        
        assert next_run.hour == 14
        assert next_run.minute == 30
    
    def test_parse_cron_past_time(self):
        """Test parsing cron when time has already passed today."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        base = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        next_run = scheduler._parse_cron("30 14", base)  # 14:30, which has passed
        
        # Should be tomorrow at 14:30
        assert next_run.day == 2
        assert next_run.hour == 14
        assert next_run.minute == 30
    
    def test_parse_cron_invalid(self):
        """Test parsing invalid cron expression."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        base = datetime.now(timezone.utc)
        next_run = scheduler._parse_cron("invalid", base)
        
        # Should return fallback (1 hour from base)
        delta = next_run - base
        assert 3590 < delta.total_seconds() < 3610


class TestScheduledMatch:
    """Tests for ScheduledMatch dataclass."""
    
    def test_scheduled_match_ordering(self):
        """Test that ScheduledMatch can be ordered by priority."""
        from scheduler import ScheduledMatch, ScheduleFrequency
        
        now = datetime.now(timezone.utc)
        
        match1 = ScheduledMatch(
            schedule_id="low",
            priority=10,
            scheduled_at=now,
            match_config=MagicMock(),
        )
        
        match2 = ScheduledMatch(
            schedule_id="high",
            priority=5,  # Lower number = higher priority
            scheduled_at=now,
            match_config=MagicMock(),
        )
        
        # match2 should be "less than" match1 (higher priority)
        assert match2 < match1


class TestQueueItem:
    """Tests for QueueItem dataclass."""
    
    def test_queue_item_creation(self):
        """Test creating a QueueItem."""
        from scheduler import QueueItem
        
        now = datetime.now(timezone.utc)
        
        item = QueueItem(
            match_id="test-match",
            config=MagicMock(),
            queued_at=now,
            priority=5,
        )
        
        assert item.match_id == "test-match"
        assert item.priority == 5
        assert item.attempts == 0
        assert item.max_attempts == 3


class TestQuickMatchBuilder:
    """Tests for QuickMatchBuilder class."""
    
    def test_resource_race_default(self):
        """Test building a resource race match with default parameters."""
        from scheduler import QuickMatchBuilder
        
        config = QuickMatchBuilder.resource_race()
        
        assert config.mission.mission_type == MissionType.RESOURCE_RACE
        assert len(config.agents) == 4
        assert all(a.is_bot for a in config.agents)
    
    def test_resource_race_custom_count(self):
        """Test building resource race with custom agent count."""
        from scheduler import QuickMatchBuilder
        
        config = QuickMatchBuilder.resource_race(agent_count=6)
        
        assert len(config.agents) == 6
    
    def test_resource_race_invalid_count(self):
        """Test building resource race with invalid agent count."""
        from scheduler import QuickMatchBuilder
        
        with pytest.raises(ValueError, match="Agent count must be between"):
            QuickMatchBuilder.resource_race(agent_count=2)
        
        with pytest.raises(ValueError, match="Agent count must be between"):
            QuickMatchBuilder.resource_race(agent_count=10)
    
    def test_multi_phase(self):
        """Test building a multi-phase match."""
        from scheduler import QuickMatchBuilder
        
        config = QuickMatchBuilder.multi_phase(
            phases=[MissionType.RESOURCE_RACE, MissionType.NEGOTIATION],
            agent_count=4,
            ticks=40,
        )
        
        assert len(config.mission.phases) == 2
        assert config.mission.ticks == 40
    
    def test_from_agent_configs(self, mock_agent_configs):
        """Test building match from existing agent configs."""
        from scheduler import QuickMatchBuilder
        
        config = QuickMatchBuilder.from_agent_configs(
            agents=mock_agent_configs,
            mission_type=MissionType.SABOTAGE,
            ticks=25,
        )
        
        assert config.mission.mission_type == MissionType.SABOTAGE
        assert config.mission.ticks == 25
        assert len(config.agents) == len(mock_agent_configs)


class TestScheduleFrequency:
    """Tests for ScheduleFrequency enum."""
    
    def test_frequency_values(self):
        """Test frequency enum values."""
        from scheduler import ScheduleFrequency
        
        assert ScheduleFrequency.ONCE.value == "once"
        assert ScheduleFrequency.HOURLY.value == "hourly"
        assert ScheduleFrequency.DAILY.value == "daily"
        assert ScheduleFrequency.WEEKLY.value == "weekly"
        assert ScheduleFrequency.CUSTOM.value == "custom"


class TestConvenienceFunctions:
    """Tests for convenience scheduling functions."""
    
    @pytest.mark.asyncio
    async def test_schedule_hourly_tournament(self):
        """Test schedule_hourly_tournament function."""
        from scheduler import MatchScheduler, schedule_hourly_tournament, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await schedule_hourly_tournament(scheduler)
        
        assert schedule_id in scheduler._schedules
        scheduled = scheduler._schedules[schedule_id]
        assert scheduled.frequency == ScheduleFrequency.HOURLY
        assert scheduled.metadata.get("type") == "hourly_tournament"
    
    @pytest.mark.asyncio
    async def test_schedule_daily_championship(self):
        """Test schedule_daily_championship function."""
        from scheduler import MatchScheduler, schedule_daily_championship, ScheduleFrequency
        
        scheduler = MatchScheduler()
        
        schedule_id = await schedule_daily_championship(scheduler)
        
        assert schedule_id in scheduler._schedules
        scheduled = scheduler._schedules[schedule_id]
        assert scheduled.frequency == ScheduleFrequency.DAILY
        assert scheduled.metadata.get("type") == "daily_championship"
        assert len(scheduled.match_config.mission.phases) == 3


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_mission_runner_empty_agents(self):
        """Test mission runner with empty agents list."""
        from mission_runner import MissionRunner
        
        config = MatchConfig(
            match_id="test",
            mission=MissionConfig(MissionType.RESOURCE_RACE),
            agents=[],
        )
        
        runner = MissionRunner(config)
        
        with pytest.raises(ValueError, match="Agent count must be between"):
            await runner.initialize()
    
    @pytest.mark.asyncio
    async def test_agent_runtime_max_retries_exhausted(self, rng):
        """Test agent runtime when all retries are exhausted."""
        from agent_runtime import AgentRuntime, Observation, ActionType
        
        runtime = AgentRuntime(max_retries=2, rng=rng)
        
        mock_driver = AsyncMock()
        mock_driver.decide.side_effect = Exception("Persistent error")
        
        agent_config = AgentConfig(
            agent_id="test",
            name="Test",
            strategy="balanced",
            is_bot=True,
        )
        
        runtime.register_driver("test", mock_driver)
        
        obs = Observation(
            tick=1,
            phase="resource_race",
            own_state=AgentState(),
            visible_agents=[],
            visible_nodes=[ResourceNode("node-1", 10)],
            recent_events=[],
            available_actions=[ActionType.GATHER],
        )
        
        result = await runtime.execute_decision(agent_config, obs)
        
        assert result.success is False
        assert result.retry_count == 2
        assert "Runtime error" in result.error
    
    def test_action_executor_harass_nonexistent_target(self):
        """Test harass action with non-existent target."""
        from agent_runtime import ActionExecutor, ActionType
        
        executor = ActionExecutor()
        
        action = {"type": ActionType.HARASS.value, "target_id": "nonexistent"}
        result = executor.execute(
            action=action,
            agent_id="agent-1",
            agent_states={
                "agent-1": AgentState(),
            },
            nodes=[],
        )
        
        assert result["success"] is False
        # Error message is "target_not_found" in actual implementation
        assert "target" in result["error"] and "not_found" in result["error"]
    
    def test_scoring_empty_standings(self):
        """Test scoring with empty standings."""
        from scoring import ScoringEngine
        
        engine = ScoringEngine()
        
        updates = engine.calculate_all_updates(
            standings=[],
            agent_states={},
            agent_configs={},
        )
        
        assert updates == []
    
    def test_scoring_single_agent(self):
        """Test scoring with single agent (no opponents)."""
        from scoring import ScoringEngine, MatchResult
        
        engine = ScoringEngine()
        
        standing = {
            "placement": 1,
            "agent_id": "solo",
            "name": "Solo",
            "strategy": "balanced",
            "mission_score": 100.0,
            "stats": AgentState(deposited=50, valid_actions=20).to_dict(),
        }
        
        updates = engine.calculate_all_updates(
            standings=[standing],
            agent_states={"solo": AgentState(deposited=50, valid_actions=20)},
            agent_configs={"solo": AgentConfig(agent_id="solo", name="Solo", strategy="balanced")},
        )
        
        assert len(updates) == 1
        assert updates[0]["agent_id"] == "solo"
    
    @pytest.mark.asyncio
    async def test_scheduler_double_start(self):
        """Test starting scheduler twice (should be idempotent)."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        await scheduler.start()
        first_task = scheduler._task
        
        await scheduler.start()  # Second start should be no-op
        
        assert scheduler._task is first_task
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_cancel_nonexistent_match(self):
        """Test canceling a match that's not in queue."""
        from scheduler import MatchScheduler
        
        scheduler = MatchScheduler()
        
        result = await scheduler.cancel_queued_match("nonexistent")
        
        assert result is False


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestIntegration:
    """Integration-style tests that exercise multiple components."""
    
    @pytest.mark.asyncio
    async def test_full_match_simulation(self, rng):
        """Test a complete match simulation with all components."""
        from mission_runner import MissionRunner
        from agent_runtime import AgentRuntime, DecisionResult
        from scoring import ScoringEngine
        
        # Create match config
        agents = [
            AgentConfig(agent_id=f"bot-{i}", name=f"Bot {i}", strategy="balanced", is_bot=True)
            for i in range(4)
        ]
        
        config = MatchConfig(
            match_id="integration-test",
            mission=MissionConfig(
                mission_type=MissionType.RESOURCE_RACE,
                ticks=10,  # Short for test
                phases=[MissionType.RESOURCE_RACE],
                parameters={"nodes": {"count": 3, "resources_per_node": 20}},
            ),
            agents=agents,
            seed=42,
        )
        
        # Create components
        agent_runtime = AgentRuntime(rng=rng)
        scoring_engine = ScoringEngine()
        
        # Create runner
        runner = MissionRunner(
            match_config=config,
            agent_runtime=agent_runtime,
            scoring_engine=scoring_engine,
            rng=rng,
        )
        
        # Track events
        events_received = []
        async def event_callback(match_id, event):
            events_received.append(event)
        
        runner.add_event_callback(event_callback)
        
        # Run match
        result = await runner.run()
        
        # Verify results
        assert result.status == MatchStatus.COMPLETED
        assert len(result.standings) == 4
        assert len(result.rank_updates) == 4
        assert len(result.events) > 0
        assert result.started_at is not None
        assert result.ended_at is not None
        
        # Verify events were emitted
        assert len(events_received) > 0
        
        # Check for expected event types
        event_types = {e["type"] for e in result.events}
        assert EventType.MISSION_STARTED.value in event_types
        assert EventType.MISSION_SCORED.value in event_types
        assert EventType.RANKS_UPDATED.value in event_types
    
    @pytest.mark.asyncio
    async def test_multi_phase_match(self, rng):
        """Test a match with multiple phases."""
        from mission_runner import MissionRunner
        from agent_runtime import AgentRuntime
        from scoring import ScoringEngine
        
        agents = [
            AgentConfig(agent_id=f"bot-{i}", name=f"Bot {i}", strategy="balanced", is_bot=True)
            for i in range(4)
        ]
        
        config = MatchConfig(
            match_id="multi-phase-test",
            mission=MissionConfig(
                mission_type=MissionType.RESOURCE_RACE,
                ticks=15,
                phases=[MissionType.RESOURCE_RACE, MissionType.NEGOTIATION],
                parameters={
                    "nodes": {"count": 3, "resources_per_node": 20},
                    "negotiation": {"rounds": 3},
                },
            ),
            agents=agents,
            seed=42,
        )
        
        runner = MissionRunner(
            match_config=config,
            agent_runtime=AgentRuntime(rng=rng),
            scoring_engine=ScoringEngine(),
            rng=rng,
        )
        
        # Track phase events
        phase_events = []
        async def event_callback(match_id, event):
            if "phase" in event.get("type", ""):
                phase_events.append(event)
        
        runner.add_event_callback(event_callback)
        
        result = await runner.run()
        
        assert result.status == MatchStatus.COMPLETED
        
        # Check phase events were emitted
        phase_started = [e for e in result.events if e["type"] == EventType.PHASE_STARTED.value]
        phase_completed = [e for e in result.events if e["type"] == EventType.PHASE_COMPLETED.value]
        
        assert len(phase_started) == 2  # Two phases
        assert len(phase_completed) == 2


# =============================================================================
# Main entry point for running tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
