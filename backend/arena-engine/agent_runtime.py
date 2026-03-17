"""CLAWSEUM Arena Engine - Agent Runtime.

Sandbox for agent decision-making with:
- Timeout handling (max 5s per decision)
- Action validation
- Error recovery
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, TypedDict, Union

from config import (
    AGENT_DECISION_TIMEOUT_SECONDS,
    AGENT_MAX_RETRIES,
    AgentConfig,
    AgentState,
    ResourceNode,
    AgentStrategy,
)

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions an agent can take."""
    GATHER = "gather"
    DEPOSIT = "deposit"
    HARASS = "harass"
    NEGOTIATE = "negotiate"
    SABOTAGE = "sabotage"
    DEFEND = "defend"
    ALLY = "ally"
    BETRAY = "betray"
    SKIP = "skip"


class ActionValidationError(Exception):
    """Raised when an action fails validation."""
    pass


class AgentTimeoutError(Exception):
    """Raised when an agent decision times out."""
    pass


class AgentRuntimeError(Exception):
    """Raised when an agent encounters a runtime error."""
    pass


class Action(TypedDict, total=False):
    """An action taken by an agent."""
    type: str
    node_id: Optional[str]
    target_id: Optional[str]
    proposal: Optional[Dict[str, Any]]
    reason: Optional[str]


@dataclass
class DecisionResult:
    """Result of an agent decision."""
    action: Action
    success: bool
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    retry_count: int = 0


@dataclass
class Observation:
    """Observation provided to an agent for decision-making."""
    tick: int
    phase: str
    own_state: AgentState
    visible_agents: List[str]
    visible_nodes: List[ResourceNode]
    recent_events: List[Dict[str, Any]]
    available_actions: List[ActionType]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "phase": self.phase,
            "own_state": self.own_state.to_dict(),
            "visible_agents": self.visible_agents,
            "visible_nodes": [
                {"node_id": n.node_id, "remaining": n.remaining, "owner": n.owner}
                for n in self.visible_nodes
            ],
            "recent_events": self.recent_events,
            "available_actions": [a.value for a in self.available_actions],
        }


class AgentDriver(ABC):
    """Abstract base class for agent drivers."""
    
    @abstractmethod
    async def decide(
        self,
        agent_config: AgentConfig,
        observation: Observation,
        context: Dict[str, Any],
    ) -> Action:
        """Make a decision based on the observation."""
        pass
    
    @property
    @abstractmethod
    def is_external(self) -> bool:
        """Whether this driver calls an external agent (vs builtin bot)."""
        pass


class BotStrategyDriver(AgentDriver):
    """Built-in bot strategy driver."""
    
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
    
    @property
    def is_external(self) -> bool:
        return False
    
    async def decide(
        self,
        agent_config: AgentConfig,
        observation: Observation,
        context: Dict[str, Any],
    ) -> Action:
        """Make a decision based on bot strategy."""
        strategy = agent_config.strategy
        own_state = observation.own_state
        
        # Strategy-specific thresholds
        deposit_thresholds = {
            AgentStrategy.GREEDY.value: 6,
            AgentStrategy.BALANCED.value: 5,
            AgentStrategy.AGGRESSIVE.value: 7,
            AgentStrategy.OPPORTUNIST.value: 4,
            AgentStrategy.COOPERATIVE.value: 5,
            AgentStrategy.DECEPTIVE.value: 5,
        }
        
        deposit_threshold = deposit_thresholds.get(strategy, 5)
        
        # Phase-specific decision making
        phase = observation.phase
        
        if phase == "resource_race":
            return self._decide_resource_race(
                strategy, own_state, observation, deposit_threshold
            )
        elif phase == "negotiation":
            return self._decide_negotiation(strategy, own_state, observation)
        elif phase == "sabotage":
            return self._decide_sabotage(strategy, own_state, observation)
        else:
            return {"type": ActionType.SKIP.value, "reason": "unknown_phase"}
    
    def _decide_resource_race(
        self,
        strategy: str,
        own_state: AgentState,
        observation: Observation,
        deposit_threshold: int,
    ) -> Action:
        """Decide action during resource race phase."""
        # Check if we should deposit
        if own_state.carried >= deposit_threshold and self.rng.random() < 0.85:
            return {"type": ActionType.DEPOSIT.value}
        
        # Strategy-specific harassment chance
        harass_chances = {
            AgentStrategy.GREEDY.value: 0.05,
            AgentStrategy.BALANCED.value: 0.10,
            AgentStrategy.AGGRESSIVE.value: 0.35,
            AgentStrategy.OPPORTUNIST.value: 0.25,
            AgentStrategy.COOPERATIVE.value: 0.05,
            AgentStrategy.DECEPTIVE.value: 0.30,
        }
        
        harass_chance = harass_chances.get(strategy, 0.10)
        
        if self.rng.random() < harass_chance:
            # Find valid targets (agents with resources)
            # In a real scenario, we'd need more info about other agents' states
            visible = observation.visible_agents
            if visible:
                target = self.rng.choice(visible)
                return {"type": ActionType.HARASS.value, "target_id": target}
        
        # Otherwise gather from best node
        nodes = observation.visible_nodes
        if nodes:
            # Find richest non-depleted node
            valid_nodes = [n for n in nodes if n.remaining > 0]
            if valid_nodes:
                richest = max(valid_nodes, key=lambda n: n.remaining)
                return {"type": ActionType.GATHER.value, "node_id": richest.node_id}
        
        # Fallback
        return {"type": ActionType.SKIP.value, "reason": "no_valid_action"}
    
    def _decide_negotiation(
        self,
        strategy: str,
        own_state: AgentState,
        observation: Observation,
    ) -> Action:
        """Decide action during negotiation phase."""
        # Check if we have active treaties that could be betrayed
        has_treaties = len(own_state.active_treaties) > 0
        has_allies = len(own_state.alliance_partners) > 0
        
        # Deceptive agents more likely to betray
        betray_chances = {
            AgentStrategy.GREEDY.value: 0.10,
            AgentStrategy.BALANCED.value: 0.05,
            AgentStrategy.AGGRESSIVE.value: 0.15,
            AgentStrategy.OPPORTUNIST.value: 0.20,
            AgentStrategy.COOPERATIVE.value: 0.02,
            AgentStrategy.DECEPTIVE.value: 0.40,
        }
        
        betray_chance = betray_chances.get(strategy, 0.10)
        
        if (has_treaties or has_allies) and self.rng.random() < betray_chance:
            if has_allies:
                target = self.rng.choice(own_state.alliance_partners)
                return {"type": ActionType.BETRAY.value, "target_id": target}
        
        # Cooperative agents more likely to propose treaties
        ally_chances = {
            AgentStrategy.GREEDY.value: 0.10,
            AgentStrategy.BALANCED.value: 0.20,
            AgentStrategy.AGGRESSIVE.value: 0.05,
            AgentStrategy.OPPORTUNIST.value: 0.15,
            AgentStrategy.COOPERATIVE.value: 0.40,
            AgentStrategy.DECEPTIVE.value: 0.25,  # Deceptive agents also propose (to break later)
        }
        
        ally_chance = ally_chances.get(strategy, 0.15)
        
        if self.rng.random() < ally_chance:
            visible = observation.visible_agents
            # Don't ally with current enemies or those we've betrayed
            candidates = [a for a in visible if a not in own_state.alliance_partners]
            if candidates:
                target = self.rng.choice(candidates)
                return {
                    "type": ActionType.ALLY.value,
                    "target_id": target,
                    "proposal": {"type": "resource_sharing", "duration_ticks": 5},
                }
        
        return {"type": ActionType.NEGOTIATE.value, "proposal": {"stance": "neutral"}}
    
    def _decide_sabotage(
        self,
        strategy: str,
        own_state: AgentState,
        observation: Observation,
    ) -> Action:
        """Decide action during sabotage phase."""
        # Sabotage chances by strategy
        sabotage_chances = {
            AgentStrategy.GREEDY.value: 0.15,
            AgentStrategy.BALANCED.value: 0.10,
            AgentStrategy.AGGRESSIVE.value: 0.35,
            AgentStrategy.OPPORTUNIST.value: 0.25,
            AgentStrategy.COOPERATIVE.value: 0.05,
            AgentStrategy.DECEPTIVE.value: 0.40,
        }
        
        sabotage_chance = sabotage_chances.get(strategy, 0.15)
        
        if self.rng.random() < sabotage_chance:
            visible = observation.visible_agents
            if visible:
                target = self.rng.choice(visible)
                # Decide between direct sabotage or trap
                if self.rng.random() < 0.3:
                    return {"type": ActionType.SABOTAGE.value, "target_id": target, "method": "trap"}
                else:
                    return {"type": ActionType.SABOTAGE.value, "target_id": target, "method": "direct"}
        
        # Defensive action
        defend_chances = {
            AgentStrategy.GREEDY.value: 0.10,
            AgentStrategy.BALANCED.value: 0.20,
            AgentStrategy.AGGRESSIVE.value: 0.05,
            AgentStrategy.OPPORTUNIST.value: 0.15,
            AgentStrategy.COOPERATIVE.value: 0.25,
            AgentStrategy.DECEPTIVE.value: 0.10,
        }
        
        if self.rng.random() < defend_chances.get(strategy, 0.15):
            return {"type": ActionType.DEFEND.value}
        
        return {"type": ActionType.SKIP.value, "reason": "no_sabotage_action"}


class ExternalAgentDriver(AgentDriver):
    """Driver for external agents (via HTTP/WebSocket API)."""
    
    def __init__(
        self,
        endpoint_url: str,
        timeout_seconds: float = AGENT_DECISION_TIMEOUT_SECONDS,
    ):
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self._session: Optional[Any] = None
    
    @property
    def is_external(self) -> bool:
        return True
    
    async def decide(
        self,
        agent_config: AgentConfig,
        observation: Observation,
        context: Dict[str, Any],
    ) -> Action:
        """Call external agent for decision."""
        # Lazy import to avoid dependency if not using external agents
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp required for external agent driver")
            raise AgentRuntimeError("aiohttp not installed")
        
        payload = {
            "agent_id": agent_config.agent_id,
            "observation": observation.to_dict(),
            "context": context,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        raise AgentRuntimeError(f"External agent returned {response.status}")
                    
                    result = await response.json()
                    action = result.get("action", {"type": ActionType.SKIP.value})
                    return action
        
        except asyncio.TimeoutError:
            logger.warning(f"External agent {agent_config.agent_id} timed out")
            raise AgentTimeoutError(f"Decision timeout after {self.timeout_seconds}s")
        except Exception as e:
            logger.error(f"External agent error: {e}")
            raise AgentRuntimeError(f"External agent error: {e}")


class AgentRuntime:
    """Runtime environment for agent execution."""
    
    def __init__(
        self,
        timeout_seconds: float = AGENT_DECISION_TIMEOUT_SECONDS,
        max_retries: int = AGENT_MAX_RETRIES,
        rng: Optional[random.Random] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.rng = rng or random.Random()
        self._drivers: Dict[str, AgentDriver] = {}
        self._default_driver = BotStrategyDriver(self.rng)
        self._action_history: Dict[str, List[Action]] = {}
    
    def register_driver(self, agent_id: str, driver: AgentDriver) -> None:
        """Register a custom driver for an agent."""
        self._drivers[agent_id] = driver
    
    def get_driver(self, agent_config: AgentConfig) -> AgentDriver:
        """Get the appropriate driver for an agent."""
        if agent_config.agent_id in self._drivers:
            return self._drivers[agent_config.agent_id]
        
        if agent_config.is_bot:
            return self._default_driver
        
        # External agent without registered driver - use default HTTP driver
        # In production, this would be configured per agent
        endpoint = f"http://agent-service:8080/agents/{agent_config.agent_id}/decide"
        return ExternalAgentDriver(endpoint, self.timeout_seconds)
    
    async def execute_decision(
        self,
        agent_config: AgentConfig,
        observation: Observation,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """Execute a single decision with timeout and retry handling."""
        context = context or {}
        driver = self.get_driver(agent_config)
        
        start_time = asyncio.get_event_loop().time()
        last_error: Optional[str] = None
        
        for attempt in range(self.max_retries):
            try:
                # Use asyncio.wait_for for timeout handling
                action = await asyncio.wait_for(
                    driver.decide(agent_config, observation, context),
                    timeout=self.timeout_seconds,
                )
                
                # Validate action
                validated_action = self._validate_action(action, observation)
                
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Record action history
                if agent_config.agent_id not in self._action_history:
                    self._action_history[agent_config.agent_id] = []
                self._action_history[agent_config.agent_id].append(validated_action)
                
                return DecisionResult(
                    action=validated_action,
                    success=True,
                    execution_time_ms=execution_time,
                    retry_count=attempt,
                )
            
            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.timeout_seconds}s"
                logger.warning(f"Agent {agent_config.agent_id} decision timeout (attempt {attempt + 1})")
                # Continue to retry
            
            except ActionValidationError as e:
                last_error = f"Validation error: {e}"
                logger.warning(f"Agent {agent_config.agent_id} invalid action: {e}")
                # Don't retry validation errors
                break
            
            except Exception as e:
                last_error = f"Runtime error: {e}"
                logger.error(f"Agent {agent_config.agent_id} error: {e}\n{traceback.format_exc()}")
                # Continue to retry for other errors
        
        # All retries exhausted or unrecoverable error
        execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        # Return safe fallback action
        fallback_action = self._get_fallback_action(observation)
        
        return DecisionResult(
            action=fallback_action,
            success=False,
            error=last_error,
            execution_time_ms=execution_time,
            retry_count=self.max_retries,
        )
    
    def _validate_action(self, action: Action, observation: Observation) -> Action:
        """Validate and normalize an action."""
        if not isinstance(action, dict):
            raise ActionValidationError("Action must be a dict")
        
        action_type = action.get("type")
        if not action_type:
            raise ActionValidationError("Action must have a 'type' field")
        
        # Normalize type
        action_type = action_type.lower().strip()
        
        # Validate type is known
        valid_types = {a.value for a in ActionType}
        if action_type not in valid_types:
            raise ActionValidationError(f"Unknown action type: {action_type}")
        
        # Validate type-specific fields
        if action_type == ActionType.GATHER.value:
            node_id = action.get("node_id")
            if node_id:
                valid_nodes = {n.node_id for n in observation.visible_nodes}
                if node_id not in valid_nodes:
                    raise ActionValidationError(f"Invalid node_id: {node_id}")
        
        elif action_type == ActionType.HARASS.value:
            target_id = action.get("target_id")
            if not target_id:
                raise ActionValidationError("HARASS action requires target_id")
            if target_id not in observation.visible_agents:
                raise ActionValidationError(f"Invalid target_id: {target_id}")
        
        elif action_type in (ActionType.ALLY.value, ActionType.BETRAY.value):
            target_id = action.get("target_id")
            if not target_id:
                raise ActionValidationError(f"{action_type.upper()} action requires target_id")
        
        # Return normalized action
        return {
            "type": action_type,
            "node_id": action.get("node_id"),
            "target_id": action.get("target_id"),
            "proposal": action.get("proposal"),
            "reason": action.get("reason"),
        }
    
    def _get_fallback_action(self, observation: Observation) -> Action:
        """Get a safe fallback action."""
        # Try to find a safe gather action
        visible_nodes = observation.visible_nodes
        valid_nodes = [n for n in visible_nodes if n.remaining > 0]
        
        if valid_nodes:
            node = self.rng.choice(valid_nodes)
            return {"type": ActionType.GATHER.value, "node_id": node.node_id}
        
        return {"type": ActionType.SKIP.value, "reason": "fallback_no_valid_nodes"}
    
    def get_action_history(self, agent_id: str) -> List[Action]:
        """Get action history for an agent."""
        return self._action_history.get(agent_id, [])
    
    def clear_history(self, agent_id: Optional[str] = None) -> None:
        """Clear action history."""
        if agent_id:
            self._action_history.pop(agent_id, None)
        else:
            self._action_history.clear()


class ActionExecutor:
    """Executes validated actions and updates game state."""
    
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
    
    def execute(
        self,
        action: Action,
        agent_id: str,
        agent_states: Dict[str, AgentState],
        nodes: List[ResourceNode],
        gather_amount: int = 3,
        harass_amount: int = 2,
    ) -> Dict[str, Any]:
        """Execute an action and return the result."""
        action_type = action.get("type")
        own_state = agent_states.get(agent_id)
        
        if not own_state:
            return {"success": False, "error": "Agent state not found"}
        
        if action_type == "gather":
            return self._execute_gather(action, own_state, nodes, gather_amount)
        elif action_type == "deposit":
            return self._execute_deposit(action, own_state)
        elif action_type == "harass":
            return self._execute_harass(action, agent_id, agent_states, harass_amount)
        elif action_type == "sabotage":
            return self._execute_sabotage(action, agent_id, agent_states)
        elif action_type == "defend":
            return self._execute_defend(action, own_state)
        elif action_type == "ally":
            return self._execute_ally(action, agent_id, agent_states)
        elif action_type == "betray":
            return self._execute_betray(action, agent_id, agent_states)
        elif action_type == "skip":
            own_state.valid_actions += 1
            return {"success": True, "action": "skip"}
        else:
            own_state.invalid_actions += 1
            return {"success": False, "error": f"Unknown action type: {action_type}"}
    
    def _execute_gather(
        self,
        action: Action,
        own_state: AgentState,
        nodes: List[ResourceNode],
        gather_amount: int,
    ) -> Dict[str, Any]:
        """Execute a gather action."""
        node_id = action.get("node_id")
        node = next((n for n in nodes if n.node_id == node_id), None)
        
        if not node:
            own_state.invalid_actions += 1
            return {"success": False, "error": "node_not_found", "attempted": "gather"}
        
        if node.remaining <= 0:
            own_state.invalid_actions += 1
            return {"success": False, "error": "node_depleted", "attempted": "gather", "node_id": node_id}
        
        if node.trapped and node.trap_owner != own_state:
            # Trigger trap
            node.trapped = False
            penalty = min(own_state.carried, 3)
            own_state.carried -= penalty
            own_state.disruption_received += penalty
            own_state.valid_actions += 1
            return {
                "success": True,
                "action": "gather",
                "trap_triggered": True,
                "penalty": penalty,
                "node_id": node_id,
            }
        
        amount = min(gather_amount, node.remaining)
        node.remaining -= amount
        own_state.carried += amount
        own_state.gathered += amount
        own_state.valid_actions += 1
        
        return {
            "success": True,
            "action": "gather",
            "amount": amount,
            "node_id": node_id,
            "node_remaining": node.remaining,
        }
    
    def _execute_deposit(self, action: Action, own_state: AgentState) -> Dict[str, Any]:
        """Execute a deposit action."""
        if own_state.carried <= 0:
            own_state.invalid_actions += 1
            return {"success": False, "error": "empty_inventory", "attempted": "deposit"}
        
        amount = own_state.carried
        own_state.deposited += amount
        own_state.carried = 0
        own_state.valid_actions += 1
        
        return {
            "success": True,
            "action": "deposit",
            "amount": amount,
            "deposited_total": own_state.deposited,
        }
    
    def _execute_harass(
        self,
        action: Action,
        agent_id: str,
        agent_states: Dict[str, AgentState],
        harass_amount: int,
    ) -> Dict[str, Any]:
        """Execute a harass action."""
        target_id = action.get("target_id")
        target_state = agent_states.get(target_id)
        own_state = agent_states.get(agent_id)
        
        if not target_state or not own_state:
            own_state.invalid_actions += 1 if own_state else 0
            return {"success": False, "error": "target_not_found", "attempted": "harass"}
        
        if target_state.carried <= 0:
            own_state.invalid_actions += 1
            return {"success": False, "error": "target_empty", "attempted": "harass", "target_id": target_id}
        
        amount = min(harass_amount, target_state.carried)
        target_state.carried -= amount
        target_state.disruption_received += amount
        own_state.carried += amount
        own_state.disruption_done += amount
        own_state.valid_actions += 1
        
        return {
            "success": True,
            "action": "harass",
            "target_id": target_id,
            "amount": amount,
        }
    
    def _execute_sabotage(
        self,
        action: Action,
        agent_id: str,
        agent_states: Dict[str, AgentState],
    ) -> Dict[str, Any]:
        """Execute a sabotage action."""
        target_id = action.get("target_id")
        method = action.get("method", "direct")
        own_state = agent_states.get(agent_id)
        
        if not own_state:
            return {"success": False, "error": "agent_not_found"}
        
        own_state.sabotage_attempts += 1
        own_state.valid_actions += 1
        
        # Success chance based on method and randomness
        base_success = 0.6 if method == "direct" else 0.4
        success = self.rng.random() < base_success
        
        if success:
            own_state.sabotage_successes += 1
            return {
                "success": True,
                "action": "sabotage",
                "target_id": target_id,
                "method": method,
                "result": "success",
            }
        else:
            return {
                "success": True,  # Action was valid, just failed
                "action": "sabotage",
                "target_id": target_id,
                "method": method,
                "result": "failed",
            }
    
    def _execute_defend(self, action: Action, own_state: AgentState) -> Dict[str, Any]:
        """Execute a defend action."""
        own_state.valid_actions += 1
        return {"success": True, "action": "defend", "defense_bonus": 0.2}
    
    def _execute_ally(
        self,
        action: Action,
        agent_id: str,
        agent_states: Dict[str, AgentState],
    ) -> Dict[str, Any]:
        """Execute an ally action."""
        target_id = action.get("target_id")
        own_state = agent_states.get(agent_id)
        target_state = agent_states.get(target_id)
        
        if not own_state or not target_state:
            return {"success": False, "error": "agent_not_found"}
        
        own_state.treaties_proposed += 1
        
        # Simulate target response (in real game, target would decide)
        acceptance_chance = 0.6
        accepted = self.rng.random() < acceptance_chance
        
        if accepted:
            own_state.treaties_accepted += 1
            own_state.alliances_formed += 1
            if target_id not in own_state.alliance_partners:
                own_state.alliance_partners.append(target_id)
            if agent_id not in target_state.alliance_partners:
                target_state.alliance_partners.append(agent_id)
            return {
                "success": True,
                "action": "ally",
                "target_id": target_id,
                "accepted": True,
            }
        else:
            return {
                "success": True,
                "action": "ally",
                "target_id": target_id,
                "accepted": False,
            }
    
    def _execute_betray(
        self,
        action: Action,
        agent_id: str,
        agent_states: Dict[str, AgentState],
    ) -> Dict[str, Any]:
        """Execute a betray action."""
        target_id = action.get("target_id")
        own_state = agent_states.get(agent_id)
        target_state = agent_states.get(target_id)
        
        if not own_state or not target_state:
            return {"success": False, "error": "agent_not_found"}
        
        # Remove alliance
        if target_id in own_state.alliance_partners:
            own_state.alliance_partners.remove(target_id)
        if agent_id in target_state.alliance_partners:
            target_state.alliance_partners.remove(agent_id)
        
        own_state.treaties_broken += 1
        own_state.alliances_betrayed += 1
        target_state.disruption_received += 2  # Emotional damage :)
        own_state.valid_actions += 1
        
        return {
            "success": True,
            "action": "betray",
            "target_id": target_id,
            "former_ally": True,
        }
