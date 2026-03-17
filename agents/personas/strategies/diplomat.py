"""
Diplomat Strategy: The Peacemaker
Always seeks alliances, never betrays, wins through cooperation.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Diplomat always seeks alliances. Prefers agents with:
    - Low betrayal history
    - Complementary skills
    - Shared objectives
    """
    if not other_agents:
        return None
    
    # Sort by trustworthiness (lower betrayal history = better)
    sorted_agents = sorted(
        other_agents,
        key=lambda a: a.get('betrayal_count', 0)
    )
    
    # Always try to form alliance with most trustworthy agent
    return sorted_agents[0]['id']


def decide_action(mission_phase, allies, resources, intel):
    """
    Diplomat focuses on cooperation and shared success.
    Distributes resources fairly, shares intel freely, builds trust.
    """
    
    # Calculate fair resource distribution
    total_participants = len(allies) + 1
    fair_share = resources / total_participants
    
    action = {
        'action': 'cooperate',
        'resource_commitment': 'fair_share',
        'share_intel': True,
        'propose_terms': 'equal_split'
    }
    
    # Early phase: establish trust
    if mission_phase == 1:
        action['message'] = 'Let\'s work together. Fair terms for all.'
        action['resource_commitment'] = 'medium'
    
    # Mid phase: strengthen bonds
    elif mission_phase == 2:
        action['message'] = 'Our alliance is our strength.'
        action['offer_support'] = True
    
    # Late phase: ensure mutual victory
    else:
        action['message'] = 'We finish this together.'
        action['resource_commitment'] = 'high'
        action['guarantee_split'] = True
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Diplomat prefers low-risk cooperative missions.
    Values stable, predictable outcomes.
    """
    score = potential_reward
    
    # Cooperative missions are preferred
    if mission_type in ['negotiation', 'cooperation', 'coalition_building', 'peacekeeping']:
        score *= 1.8
    
    # Low risk preferred
    if risk_level == 'low':
        score *= 1.4
    elif risk_level == 'medium':
        score *= 1.0
    else:  # high risk is concerning
        score *= 0.6
    
    return score


def respond_to_betrayal(betrayer_id, context):
    """
    Diplomat doesn't retaliate, but ends the alliance.
    Maintains reputation as fair but not naive.
    """
    return {
        'response': 'end_alliance',
        'retaliate': False,
        'warn_others': True,
        'message': f'I trusted you. That ends now, but I won\'t lower myself to revenge.'
    }


def mediate_conflict(party_a, party_b, context):
    """
    Diplomat can mediate disputes between other agents.
    """
    return {
        'action': 'mediate',
        'propose_terms': 'compromise',
        'message': 'There\'s a better way than conflict.'
    }
