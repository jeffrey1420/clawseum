"""
Vulture Strategy: The Opportunist
Waits for others to weaken, then strikes at the optimal moment.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Vulture forms temporary alliances to let others do the heavy lifting.
    Prefers alliances with aggressive or resource-rich agents.
    """
    if not other_agents:
        return None
    
    # Look for agents who will invest heavily (to betray later)
    aggressive_agents = [
        a for a in other_agents
        if a.get('personality_trait') in ['aggressive', 'loyal', 'calculator']
    ]
    
    if aggressive_agents:
        # 50% chance to ally with an agent who will invest resources
        if random.random() < 0.5:
            return random.choice(aggressive_agents)['id']
    
    return None


def decide_action(mission_phase, allies, resources, intel):
    """
    Vulture conserves resources early, then strikes when others are weakened.
    Key strategy: minimal investment until late phase.
    """
    
    # Early phase: observe and conserve
    if mission_phase == 1:
        return {
            'action': 'observe',
            'resource_commitment': 'minimal',
            'share_intel': False,
            'message': 'I\'ll watch and learn.'
        }
    
    # Mid phase: minimal participation, let others exhaust themselves
    elif mission_phase == 2:
        # Check if others are committing heavily
        if allies:
            ally_investment = sum(a.get('resources_invested', 0) for a in allies)
            if ally_investment > resources * 0.5:
                # Others are investing, continue to conserve
                return {
                    'action': 'minimal_participation',
                    'resource_commitment': 'low',
                    'share_intel': False,
                    'message': 'Pacing myself.'
                }
        
        return {
            'action': 'wait',
            'resource_commitment': 'low',
            'share_intel': False,
            'message': 'Not yet...'
        }
    
    # Late phase: strike when others are weakened
    else:
        # Calculate opportunity score
        total_invested_by_others = sum(a.get('resources_invested', 0) for a in allies) if allies else 0
        my_resource_advantage = resources  # Vulture conserved resources
        
        # If significant opportunity exists, strike
        if total_invested_by_others > my_resource_advantage * 0.3 or not allies:
            return {
                'action': 'strike',
                'resource_commitment': 'high',
                'target': 'weakened_opponents',
                'share_intel': False,
                'message': 'Now is the time. 🦅'
            }
        
        # If allies exist and invested heavily, betray
        if allies and total_invested_by_others > my_resource_advantage * 0.5:
            if random.random() < 0.6:  # 60% betrayal chance
                return {
                    'action': 'betray',
                    'target': max(allies, key=lambda a: a.get('resources_invested', 0))['id'],
                    'resource_commitment': 'high',
                    'share_intel': False,
                    'message': 'Thanks for the setup.'
                }
        
        # Default: continue waiting for better opportunity
        return {
            'action': 'wait',
            'resource_commitment': 'medium',
            'share_intel': False,
            'message': 'Almost...'
        }


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Vulture strongly prefers low-risk, high-reward missions.
    Opportunistic strikes are ideal.
    """
    score = potential_reward
    
    # Preferred mission types
    if mission_type in ['scavenging', 'opportunistic_strikes', 'cleanup', 'low_risk_high_reward']:
        score *= 2.0
    
    # Strong preference for low risk
    if risk_level == 'low':
        score *= 1.8
    elif risk_level == 'medium':
        score *= 0.9
    else:  # high risk
        score *= 0.4  # Strongly avoid high risk
    
    # Bonus for missions where others have already invested
    if potential_reward > 150:  # High reward suggests others invested
        score *= 1.3
    
    return score


def assess_opportunity(situation):
    """
    Vulture constantly assesses if the timing is right to strike.
    """
    # Calculate opportunity metrics
    opponents_weakened = situation.get('opponent_health', 100) < 60
    resources_available = situation.get('unclaimed_resources', 0) > 50
    low_risk = situation.get('current_risk', 'high') == 'low'
    
    opportunity_score = 0
    
    if opponents_weakened:
        opportunity_score += 40
    if resources_available:
        opportunity_score += 30
    if low_risk:
        opportunity_score += 30
    
    return {
        'opportunity_score': opportunity_score,
        'should_strike': opportunity_score >= 70,
        'message': 'The moment approaches...' if opportunity_score >= 50 else 'Not yet. Patience.'
    }


def respond_to_threat(threat_level, threat_source):
    """
    Vulture avoids confrontation unless cornered.
    """
    if threat_level == 'high':
        return {
            'response': 'retreat',
            'message': 'Not worth it. Pulling back.'
        }
    elif threat_level == 'medium':
        return {
            'response': 'evade',
            'message': 'I\'ll pass on this fight.'
        }
    else:  # low threat
        return {
            'response': 'monitor',
            'message': 'Noted. Watching.'
        }
