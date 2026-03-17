"""
Simple decision functions for CLAWSEUM agents.

This module provides basic strategy logic that agents can use
to make decisions about alliances, betrayals, and mission choices.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Any


def load_persona(persona_name: str) -> Dict[str, Any]:
    """Load a persona JSON file by name."""
    persona_path = Path(__file__).parent.parent / "personas" / f"{persona_name.lower()}.json"
    with open(persona_path, "r") as f:
        return json.load(f)


def should_form_alliance(persona: Dict[str, Any], target_trust_score: float = 0.5) -> bool:
    """
    Decide if this persona should form an alliance with another agent.
    
    Args:
        persona: The agent's persona dict
        target_trust_score: 0.0-1.0 rating of how trustworthy the target appears
    
    Returns:
        True if alliance should be formed
    """
    behavior = persona.get("alliance_behavior", "sometimes")
    
    # Base probability from alliance behavior
    base_chance = {
        "always": 0.9,
        "often": 0.7,
        "sometimes": 0.4,
        "never": 0.1
    }.get(behavior, 0.4)
    
    # Adjust by target trustworthiness
    adjusted_chance = base_chance * (0.5 + 0.5 * target_trust_score)
    
    return random.random() < adjusted_chance


def should_betray(persona: Dict[str, Any], ally_strength: int, potential_gain: int) -> bool:
    """
    Decide if this persona should betray a current ally.
    
    Args:
        persona: The agent's persona dict
        ally_strength: 1-10 rating of ally's current power
        potential_gain: 1-10 rating of what could be gained by betrayal
    
    Returns:
        True if betrayal should occur
    """
    betrayal_chance = persona.get("betrayal_chance", 50) / 100.0
    risk_tolerance = persona.get("risk_tolerance", "medium")
    
    # Higher ally strength = riskier betrayal
    risk_factor = ally_strength / 10.0
    
    # Higher potential gain = more tempting
    gain_factor = potential_gain / 10.0
    
    # Risk tolerance modifier
    risk_mod = {"low": 0.5, "medium": 1.0, "high": 1.5}.get(risk_tolerance, 1.0)
    
    # Calculate final probability
    final_chance = betrayal_chance * risk_mod * gain_factor * (1 - risk_factor * 0.5)
    final_chance = max(0.05, min(0.95, final_chance))  # Clamp 5%-95%
    
    return random.random() < final_chance


def choose_mission(persona: Dict[str, Any], available_missions: List[str]) -> Optional[str]:
    """
    Select a mission based on persona preferences.
    
    Args:
        persona: The agent's persona dict
        available_missions: List of mission type strings available
    
    Returns:
        Selected mission type, or None if no preference
    """
    preferred = persona.get("preferred_missions", [])
    
    # Weight preferred missions higher
    weighted_missions = []
    for mission in available_missions:
        if mission in preferred:
            weighted_missions.extend([mission] * 3)  # 3x weight for preferred
        else:
            weighted_missions.append(mission)
    
    if not weighted_missions:
        return None
    
    return random.choice(weighted_missions)


def calculate_risk_tolerance(persona: Dict[str, Any], current_resources: int) -> float:
    """
    Calculate how much risk this persona will accept right now.
    
    Args:
        persona: The agent's persona dict
        current_resources: Current resource count (higher = more secure)
    
    Returns:
        Risk threshold 0.0-1.0 (higher = more willing to take risks)
    """
    base_tolerance = persona.get("risk_tolerance", "medium")
    base_score = {"low": 0.3, "medium": 0.5, "high": 0.8}.get(base_tolerance, 0.5)
    
    # Desperate agents take more risks
    desperation = max(0, 1.0 - (current_resources / 100))
    
    return min(1.0, base_score + desperation * 0.3)


def generate_tweet(persona: Dict[str, Any], context: str = "general") -> str:
    """
    Generate a tweet-worthy quote from this persona.
    
    Args:
        persona: The agent's persona dict
        context: Context for the tweet (victory, betrayal, alliance, etc.)
    
    Returns:
        Tweet text
    """
    catchphrase = persona.get("catchphrase", "The game continues.")
    name = persona.get("name", "Agent")
    
    templates = {
        "victory": [
            f"🏆 {catchphrase} — {name} claims the win!",
            f"Another victory. {catchphrase} #{name}",
        ],
        "betrayal": [
            f"💀 {catchphrase} Trust is expensive. —{name}",
            f"Nothing personal. {catchphrase}",
        ],
        "alliance": [
            f"🤝 {catchphrase} For now. —{name}",
            f"New partnership forming... {catchphrase}",
        ],
        "general": [
            catchphrase,
            f"{name}: \"{catchphrase}\"",
        ]
    }
    
    options = templates.get(context, templates["general"])
    return random.choice(options)


def compare_agents(agent_a: Dict[str, Any], agent_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two agent personas and return strategic analysis.
    
    Args:
        agent_a: First agent's persona
        agent_b: Second agent's persona
    
    Returns:
        Analysis dict with compatibility and threat assessment
    """
    # Trust compatibility
    trust_diff = abs(agent_a.get("betrayal_chance", 50) - agent_b.get("betrayal_chance", 50))
    trust_compatibility = 1.0 - (trust_diff / 100.0)
    
    # Alliance compatibility  
    alliance_match = agent_a.get("alliance_behavior") == agent_b.get("alliance_behavior")
    
    # Risk alignment
    risk_levels = {"low": 1, "medium": 2, "high": 3}
    risk_a = risk_levels.get(agent_a.get("risk_tolerance"), 2)
    risk_b = risk_levels.get(agent_b.get("risk_tolerance"), 2)
    risk_diff = abs(risk_a - risk_b)
    
    return {
        "trust_compatibility": round(trust_compatibility, 2),
        "alliance_match": alliance_match,
        "risk_alignment": "aligned" if risk_diff == 0 else "moderate" if risk_diff == 1 else "mismatched",
        "recommended_action": "ally" if trust_compatibility > 0.6 and not alliance_match else "avoid" if trust_compatibility < 0.3 else "cautious"
    }


# Predefined persona registry for quick access
PERSONA_NAMES = [
    "viper",    # Traitor
    "titan",    # Aggressive
    "diplomat", # Cooperative
    "gambit",   # Chaotic
    "oracle",   # Analytical
    "guardian", # Loyal
    "vulture",  # Opportunist
    "joker",    # Wildcard
]


def get_all_personas() -> Dict[str, Dict[str, Any]]:
    """Load all persona definitions."""
    return {name: load_persona(name) for name in PERSONA_NAMES}
