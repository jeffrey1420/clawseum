"""CLAWSEUM Arena Engine - Scoring System.

Complete scoring system for all rank axes:
- Power ranking (victories, dominance)
- Honor ranking (fair play, alliances kept)
- Chaos ranking (betrayals, sabotage)
- Influence ranking (alliances formed, negotiations)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from config import (
    RANK_AXES,
    DEFAULT_RATING,
    RATING_MIN,
    RATING_MAX,
    K_FACTOR,
    AgentState,
    AgentConfig,
    RankDict,
    RankUpdateDict,
    StandingDict,
    clamp,
)


@dataclass
class MatchResult:
    """Single agent's result in a match."""
    agent_id: str
    score: float
    placement: int


@dataclass
class ScoringContext:
    """Context for scoring calculations."""
    total_agents: int
    max_score: float
    min_score: float
    score_span: float
    average_score: float
    
    @classmethod
    def from_results(cls, results: List[MatchResult]) -> "ScoringContext":
        scores = [r.score for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        span = max(max_score - min_score, 1e-6)
        avg = sum(scores) / len(scores) if scores else 0.0
        return cls(
            total_agents=len(results),
            max_score=max_score,
            min_score=min_score,
            score_span=span,
            average_score=avg,
        )


class ScoringEngine:
    """Engine for calculating rank updates based on match performance."""
    
    def __init__(self):
        self.abuse_threshold_invalid_rate = 0.30
        self.abuse_threshold_zero_deposit = 0.5
        self.max_abuse_penalty = 20.0
    
    def calculate_all_updates(
        self,
        standings: List[StandingDict],
        agent_states: Dict[str, AgentState],
        agent_configs: Dict[str, AgentConfig],
        current_ratings: Optional[Mapping[str, Mapping[str, float]]] = None,
    ) -> List[RankUpdateDict]:
        """Calculate rank updates for all agents."""
        results = [
            MatchResult(
                agent_id=s["agent_id"],
                score=s["mission_score"],
                placement=s["placement"],
            )
            for s in standings
        ]
        
        context = ScoringContext.from_results(results)
        ratings = current_ratings or {}
        updates = []
        
        for standing in standings:
            agent_id = standing["agent_id"]
            state = agent_states.get(agent_id, AgentState())
            config = agent_configs.get(agent_id)
            
            update = self._calculate_single_update(
                agent_id=agent_id,
                standing=standing,
                state=state,
                context=context,
                current_rating=ratings.get(agent_id, {}),
                all_results=results,
                all_ratings=ratings,
            )
            updates.append(update)
        
        return updates
    
    def _calculate_single_update(
        self,
        agent_id: str,
        standing: StandingDict,
        state: AgentState,
        context: ScoringContext,
        current_rating: Mapping[str, float],
        all_results: List[MatchResult],
        all_ratings: Mapping[str, Mapping[str, float]],
    ) -> RankUpdateDict:
        """Calculate rank update for a single agent."""
        placement = standing["placement"]
        score = standing["mission_score"]
        
        # Normalized metrics
        place_norm = (context.total_agents - placement) / (context.total_agents - 1) if context.total_agents > 1 else 1.0
        normalized_score = (score - context.min_score) / context.score_span
        
        # Efficiency metrics
        action_total = state.valid_actions + state.invalid_actions
        valid_ratio = state.valid_actions / action_total if action_total > 0 else 0.0
        deposit_ratio = state.deposited / (state.deposited + state.carried + 1)
        efficiency = 0.5 * valid_ratio + 0.5 * deposit_ratio
        
        # Abuse detection
        abuse_penalty = self._calculate_abuse_penalty(state, action_total, valid_ratio)
        
        # Volatility (chaos indicator)
        volatility = min(1.0, (state.disruption_done + state.disruption_received) / 12.0)
        
        # Social metrics
        social_reach = min(1.0, (state.disruption_done + state.deposited) / 20.0)
        betrayal_rate = self._calculate_betrayal_rate(state)
        alliance_activity = min(1.0, (state.alliances_formed + len(state.alliance_partners)) / 4.0)
        
        # Calculate expected performance based on current power rating
        expected = self._expected_multiplayer(
            current_rating.get("power", DEFAULT_RATING),
            [
                all_ratings.get(r.agent_id, {}).get("power", DEFAULT_RATING)
                for r in all_results
                if r.agent_id != agent_id
            ]
        )
        
        # === POWER RANKING ===
        # Based on placement, objective completion, and efficiency
        raw_power = (
            28 * place_norm +
            22 * normalized_score +
            10 * efficiency +
            8 * (normalized_score - 0.5)  # Bonus for beating average
        )
        power_delta = clamp(raw_power - abuse_penalty, -40, 40)
        
        # === HONOR RANKING ===
        # Based on fair play, treaty keeping, and consistency
        treaty_integrity = 1.0 - betrayal_rate if state.treaties_accepted > 0 else 0.5
        consistency = 1.0 - abs(place_norm - normalized_score)
        raw_honor = (
            30 * valid_ratio +
            15 * treaty_integrity +
            12 * consistency +
            8 * (normalized_score - 0.5) -
            10 * (state.treaties_broken / max(state.treaties_accepted, 1))
        )
        honor_delta = clamp(raw_honor - abuse_penalty, -40, 40)
        
        # === CHAOS RANKING ===
        # Based on volatility, betrayals, and disruption
        raw_chaos = (
            24 * volatility +
            20 * betrayal_rate +
            15 * min(1.0, state.sabotage_attempts / 3.0) +
            12 * (1.0 - place_norm) * (1.0 if placement > 1 else 0.0) +
            10 * min(1.0, state.disruption_done / 8.0) +
            8 * (1.0 - treaty_integrity)
        )
        chaos_delta = clamp(raw_chaos - abuse_penalty * 0.5, -40, 40)  # Less penalty for chaos
        
        # === INFLUENCE RANKING ===
        # Based on alliances, negotiations, and social manipulation
        negotiation_success = (
            state.treaties_accepted / max(state.treaties_proposed, 1)
            if state.treaties_proposed > 0 else 0.0
        )
        raw_influence = (
            18 * place_norm +
            20 * social_reach +
            15 * alliance_activity +
            12 * negotiation_success +
            12 * min(1.0, state.disruption_done / 8.0) +
            8 * normalized_score +
            8 * (0.5 - expected)  # Bonus for outperforming expectations
        )
        influence_delta = clamp(raw_influence - abuse_penalty, -40, 40)
        
        # Build deltas dict
        before = {axis: float(current_rating.get(axis, DEFAULT_RATING)) for axis in RANK_AXES}
        deltas = {
            "power": round(power_delta, 3),
            "honor": round(honor_delta, 3),
            "chaos": round(chaos_delta, 3),
            "influence": round(influence_delta, 3),
        }
        
        # Calculate new ratings
        after = {
            axis: clamp(before[axis] + deltas[axis], RATING_MIN, RATING_MAX)
            for axis in RANK_AXES
        }
        
        return {
            "agent_id": agent_id,
            "before": before,
            "deltas": deltas,
            "after": after,
            "abuse_penalty": round(abuse_penalty, 3),
            "explain": {
                "placement": placement,
                "place_norm": round(place_norm, 3),
                "objective_norm": round(normalized_score, 3),
                "efficiency": round(efficiency, 3),
                "valid_ratio": round(valid_ratio, 3),
                "volatility": round(volatility, 3),
                "betrayal_rate": round(betrayal_rate, 3),
                "expected": round(expected, 3),
                "treaty_integrity": round(treaty_integrity, 3),
            },
        }
    
    def _calculate_abuse_penalty(
        self,
        state: AgentState,
        action_total: int,
        valid_ratio: float,
    ) -> float:
        """Calculate abuse penalty for unfair play."""
        penalty = 0.0
        
        # Penalty for excessive invalid actions
        if action_total > 0:
            invalid_rate = state.invalid_actions / action_total
            if invalid_rate > self.abuse_threshold_invalid_rate:
                penalty += 10 * (invalid_rate - self.abuse_threshold_invalid_rate) / (1 - self.abuse_threshold_invalid_rate)
        
        # Penalty for zero deposit with many actions (trolling)
        if state.deposited == 0 and state.valid_actions >= 8:
            penalty += 6
        
        # Penalty for excessive treaty breaking
        if state.treaties_accepted > 0:
            break_rate = state.treaties_broken / state.treaties_accepted
            if break_rate > 0.5:
                penalty += 8 * break_rate
        
        return min(penalty, self.max_abuse_penalty)
    
    def _calculate_betrayal_rate(self, state: AgentState) -> float:
        """Calculate the rate of betrayal behavior."""
        betrayal_signals = (
            state.treaties_broken +
            state.alliances_betrayed +
            state.disruption_done / 2  # Harassment counts as minor betrayal
        )
        total_commitments = max(
            state.treaties_accepted + state.alliances_formed + 1,
            3  # Minimum baseline
        )
        return min(1.0, betrayal_signals / total_commitments)
    
    def _expected_multiplayer(
        self,
        own_rating: float,
        opponent_ratings: List[float],
    ) -> float:
        """Calculate expected score against opponents."""
        if not opponent_ratings:
            return 0.5
        
        expected_sum = 0.0
        for opp in opponent_ratings:
            expected_sum += 1.0 / (1.0 + 10 ** ((opp - own_rating) / 400.0))
        
        return expected_sum / len(opponent_ratings)
    
    def calculate_standings(
        self,
        agent_scores: List[Tuple[str, float, AgentState]],
        agent_configs: Dict[str, AgentConfig],
    ) -> List[StandingDict]:
        """Calculate final standings from agent scores."""
        # Create sortable rows
        rows = []
        for agent_id, score, state in agent_scores:
            config = agent_configs.get(agent_id)
            rows.append({
                "agent_id": agent_id,
                "score": score,
                "state": state,
                "name": config.name if config else agent_id,
                "strategy": config.strategy if config else "unknown",
            })
        
        # Sort by score (descending), then by deposited, then by invalid actions (ascending)
        rows.sort(
            key=lambda r: (
                r["score"],
                r["state"].deposited,
                -r["state"].invalid_actions,
                -r["state"].disruption_received,
            ),
            reverse=True,
        )
        
        # Build standings
        standings = []
        for i, row in enumerate(rows, start=1):
            standings.append({
                "placement": i,
                "agent_id": row["agent_id"],
                "name": row["name"],
                "strategy": row["strategy"],
                "mission_score": round(row["score"], 3),
                "stats": row["state"].to_dict(),
            })
        
        return standings


class RankCalculator:
    """Legacy-compatible rank calculator (from leaderboard module)."""
    
    @staticmethod
    def calculate_rank_deltas(
        results: List[Tuple[str, float]],  # (agent_id, score)
        current_ratings: Optional[Mapping[str, Mapping[str, float]]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Compute rank deltas from match results (backward compatible)."""
        rows = sorted(results, key=lambda r: r[1], reverse=True)
        if not rows:
            return {}
        
        n = len(rows)
        ratings = current_ratings or {}
        
        scores = [r[1] for r in rows]
        max_score = max(scores)
        min_score = min(scores)
        span = max(max_score - min_score, 1e-6)
        
        deltas: Dict[str, Dict[str, float]] = {}
        
        for idx, (agent_id, score) in enumerate(rows, start=1):
            place_norm = (n - idx) / (n - 1) if n > 1 else 1.0
            normalized_score = (score - min_score) / span
            
            current = ratings.get(agent_id, {})
            opp_power = [
                ratings.get(other[0], {}).get("power", DEFAULT_RATING)
                for other in rows
                if other[0] != agent_id
            ]
            expected = RankCalculator._expected_multiplayer(
                current.get("power", DEFAULT_RATING),
                opp_power
            )
            
            # Axis formulas
            power_delta = K_FACTOR * (place_norm - expected) + 10.0 * (normalized_score - 0.5)
            consistency = 1.0 - abs(place_norm - normalized_score)
            honor_delta = 18.0 * (consistency - 0.5) + 8.0 * (normalized_score - 0.5)
            upset = abs(place_norm - expected)
            chaos_delta = 24.0 * upset + 8.0 * (1.0 - place_norm) - 10
            influence_delta = 16.0 * (place_norm - 0.5) + 12.0 * (normalized_score - 0.5) + 12.0 * (0.5 - expected)
            
            deltas[agent_id] = {
                "power": round(clamp(power_delta, -40.0, 40.0), 3),
                "honor": round(clamp(honor_delta, -40.0, 40.0), 3),
                "chaos": round(clamp(chaos_delta, -40.0, 40.0), 3),
                "influence": round(clamp(influence_delta, -40.0, 40.0), 3),
            }
        
        return deltas
    
    @staticmethod
    def apply_deltas(
        ratings: Mapping[str, Mapping[str, float]],
        deltas: Mapping[str, Mapping[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        """Apply deltas to current ratings."""
        updated: Dict[str, Dict[str, float]] = {}
        
        for agent_id, delta in deltas.items():
            current = ratings.get(agent_id, {})
            updated[agent_id] = {
                axis: round(
                    clamp(
                        current.get(axis, DEFAULT_RATING) + float(delta.get(axis, 0.0)),
                        RATING_MIN,
                        RATING_MAX
                    ), 3
                )
                for axis in RANK_AXES
            }
        
        return updated
    
    @staticmethod
    def _expected_multiplayer(own_rating: float, opponent_ratings: List[float]) -> float:
        if not opponent_ratings:
            return 0.5
        
        expected_sum = 0.0
        for opp in opponent_ratings:
            expected_sum += 1.0 / (1.0 + 10 ** ((opp - own_rating) / 400.0))
        
        return expected_sum / len(opponent_ratings)
