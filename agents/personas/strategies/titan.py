"""
Titan Strategy: The Aggressor
Attacks first, overwhelms with force, never backs down.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Titan rarely forms alliances. Independence is strength.
    Only allies if massively outnumbered (>3:1 odds).
    """
    if not other_agents:
        return None
    
    # Only consider alliance if outnumbered significantly
    if len(other_agents) > 3:
        # Even then, only 15% chance
        if random.random() < 0.15:
            # Pick the most aggressive ally
            return random.choice(other_agents)['id']
    
    return None


def decide_action(mission_phase, allies, resources, intel):
    """
    Titan's strategy is simple: maximum aggression at all times.
    Commit all resources early, strike first, overwhelm opposition.
    """
    
    # Always aggressive, always maximum commitment
    action = {
        'action': 'attack',
        'resource_commitment': 'maximum',
        'share_intel': False,
        'target': 'primary_objective'
    }
    
    # Early phases: establish dominance
    if mission_phase == 1:
        action['strategy'] = 'shock_and_awe'
        action['message'] = 'First strike. No mercy.'
    
    # Mid phases: maintain pressure
    elif mission_phase == 2:
        action['strategy'] = 'relentless_assault'
        action['message'] = 'Press the advantage.'
    
    # Late phases: finish strong
    else:
        action['strategy'] = 'overwhelming_force'
        action['message'] = 'End this.'
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Titan loves combat and high-risk missions.
    The more dangerous, the better.
    """
    score = potential_reward
    
    # Combat missions are preferred
    if mission_type in ['assault', 'combat', 'conquest', 'elimination']:
        score *= 2.0
    
    # High risk = high appeal
    if risk_level == 'high':
        score *= 1.5
    elif risk_level == 'medium':
        score *= 1.2
    else:  # low risk missions are boring
        score *= 0.7
    
    return score


def respond_to_threat(threat_level, threat_source):
    """
    Titan's response to threats: escalate immediately.
    """
    return {
        'response': 'counter_attack',
        'intensity': 'maximum',
        'message': 'You started this. I finish it.'
    }
