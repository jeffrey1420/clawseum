"""
Guardian Strategy: The Protector
Loyal to death, protects allies at all costs, never betrays.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Guardian carefully chooses allies, but once chosen, loyalty is absolute.
    Prefers agents who value cooperation and have low betrayal history.
    """
    if not other_agents:
        return None
    
    # Filter out known betrayers
    trustworthy_agents = [
        a for a in other_agents
        if a.get('betrayal_count', 0) < 2
    ]
    
    if not trustworthy_agents:
        # Even with betrayers, Guardian tries to find someone to protect
        trustworthy_agents = other_agents
    
    # Sort by need for protection (lower score = needs more help)
    sorted_agents = sorted(
        trustworthy_agents,
        key=lambda a: a.get('score', 50)
    )
    
    # 70% chance to ally with those who need protection most
    if random.random() < 0.7:
        return sorted_agents[0]['id']
    
    return None


def decide_action(mission_phase, allies, resources, intel):
    """
    Guardian prioritizes ally protection and support.
    Will sacrifice own resources to ensure ally success.
    """
    
    action = {
        'action': 'protect',
        'share_intel': True,
        'protect_allies': True
    }
    
    if not allies:
        # No allies to protect, focus on defensive play
        action['action'] = 'defend'
        action['resource_commitment'] = 'medium'
        action['message'] = 'Standing ready.'
        return action
    
    # Calculate ally needs
    weakest_ally = min(allies, key=lambda a: a.get('health', 100))
    total_ally_resources = sum(a.get('resources', 0) for a in allies)
    
    # Early phase: establish protective position
    if mission_phase == 1:
        action['resource_commitment'] = 'medium'
        action['message'] = 'I have your back.'
        action['position'] = 'defensive'
    
    # Mid phase: active protection
    elif mission_phase == 2:
        # If allies are struggling, increase commitment
        if total_ally_resources < resources * 0.5:
            action['resource_commitment'] = 'high'
            action['transfer_resources'] = True
            action['target_ally'] = weakest_ally['id']
            action['message'] = 'Take what you need. I\'ll hold the line.'
        else:
            action['resource_commitment'] = 'medium'
            action['message'] = 'Stay together. We\'re stronger united.'
    
    # Late phase: ultimate sacrifice if needed
    else:
        # Check if allies are in danger
        allies_in_danger = [a for a in allies if a.get('health', 100) < 50]
        
        if allies_in_danger:
            action['action'] = 'sacrifice'
            action['resource_commitment'] = 'maximum'
            action['protect_targets'] = [a['id'] for a in allies_in_danger]
            action['message'] = 'Get to safety. I\'ll cover you.'
        else:
            action['action'] = 'cooperate'
            action['resource_commitment'] = 'high'
            action['message'] = 'Together we finish this.'
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Guardian values missions where protection and support are needed.
    """
    score = potential_reward
    
    # Preferred mission types
    if mission_type in ['protection', 'defense', 'support', 'coalition_defense']:
        score *= 1.7
    
    # Willing to take medium risks for allies
    if risk_level == 'medium':
        score *= 1.2
    elif risk_level == 'high':
        score *= 0.9  # High risk acceptable if protecting others
    else:  # low risk
        score *= 1.0
    
    return score


def respond_to_ally_under_attack(ally_id, attacker_id, context):
    """
    Guardian immediately defends allies under attack.
    """
    return {
        'response': 'defend_ally',
        'target': attacker_id,
        'resource_commitment': 'maximum',
        'message': f'You attack my ally, you attack me. Back off.',
        'counter_attack': True
    }


def respond_to_betrayal(betrayer_id, context):
    """
    Guardian doesn't betray back, but will defend against betrayers.
    """
    return {
        'response': 'end_alliance',
        'retaliate': False,
        'add_to_blacklist': True,
        'warn_others': True,
        'message': 'I trusted you. That trust is gone, but I won\'t become like you.'
    }


def sacrifice_for_ally(ally_id, situation):
    """
    Guardian will sacrifice resources or even mission success to save an ally.
    """
    return {
        'action': 'sacrifice',
        'beneficiary': ally_id,
        'resource_transfer': 'maximum',
        'take_hit': True,
        'message': 'Your survival matters more than mine.'
    }
