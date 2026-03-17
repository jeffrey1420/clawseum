"""
Viper Strategy: The Betrayer
Builds alliances to gather intel, then betrays at the optimal moment.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Viper joins alliances often to build trust and gather information.
    Prefers alliances with stronger agents to maximize betrayal impact.
    """
    if not other_agents:
        return None
    
    # Sort by apparent strength/score
    sorted_agents = sorted(other_agents, key=lambda a: a.get('score', 0), reverse=True)
    
    # 75% chance to join alliance with top agent
    if random.random() < 0.75:
        return sorted_agents[0]['id']
    
    return None


def decide_action(mission_phase, allies, resources, intel):
    """
    Viper plays along until the critical moment, then betrays.
    Betrayal triggers when:
    - Mission is near completion (phase >= 3)
    - Allies have invested significant resources
    - Betrayal would yield maximum gain
    """
    
    # Early phases: play cooperative
    if mission_phase < 3:
        return {
            'action': 'cooperate',
            'resource_commitment': 'medium',
            'share_intel': True
        }
    
    # Calculate betrayal value
    ally_investment = sum(a.get('resources_invested', 0) for a in allies)
    betrayal_value = ally_investment * 0.85  # 85% betrayal probability
    
    # Critical phase: betray if conditions are right
    if mission_phase >= 3 and ally_investment > resources * 0.5:
        if random.random() < 0.85:  # 85% betrayal chance
            return {
                'action': 'betray',
                'target': max(allies, key=lambda a: a.get('resources_invested', 0))['id'],
                'resource_commitment': 'high',
                'share_intel': False
            }
    
    # Default: keep building trust
    return {
        'action': 'cooperate',
        'resource_commitment': 'high',
        'share_intel': True
    }


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Viper loves high-risk missions with betrayal opportunities.
    Infiltration and sabotage missions are preferred.
    """
    score = potential_reward
    
    if mission_type in ['infiltration', 'sabotage', 'intelligence_gathering']:
        score *= 1.5
    
    if risk_level == 'high':
        score *= 1.3
    
    return score
