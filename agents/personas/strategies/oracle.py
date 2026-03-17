"""
Oracle Strategy: The Calculator
Analyzes patterns, calculates probabilities, makes optimal decisions.
"""

import random

def calculate_expected_value(action, context):
    """
    Helper function to calculate expected value of an action.
    """
    probability_success = context.get('success_rate', 0.5)
    reward = context.get('reward', 0)
    cost = context.get('cost', 0)
    
    ev = (probability_success * reward) - cost
    return ev


def decide_alliance(mission_context, other_agents):
    """
    Oracle calculates the expected value of each potential alliance.
    Forms alliance only if EV > solo play.
    """
    if not other_agents:
        return None
    
    # Calculate solo play EV
    solo_ev = mission_context.get('base_reward', 100) * mission_context.get('solo_success_rate', 0.4)
    
    # Calculate alliance EVs
    best_ally = None
    best_ev = solo_ev
    
    for agent in other_agents:
        # Alliance increases success rate but splits reward
        alliance_success_rate = min(0.9, mission_context.get('solo_success_rate', 0.4) + 0.3)
        alliance_reward = mission_context.get('base_reward', 100) * 0.5  # split
        ally_ev = alliance_success_rate * alliance_reward
        
        # Factor in betrayal risk
        betrayal_risk = agent.get('betrayal_probability', 0.3) / 100
        adjusted_ev = ally_ev * (1 - betrayal_risk)
        
        if adjusted_ev > best_ev:
            best_ev = adjusted_ev
            best_ally = agent['id']
    
    return best_ally


def decide_action(mission_phase, allies, resources, intel):
    """
    Oracle calculates optimal action based on:
    - Resource efficiency
    - Success probability
    - Expected value maximization
    - Risk-adjusted returns
    """
    
    # Gather data points
    total_resources = resources
    phase_progress = mission_phase / 5.0  # Assume 5 phases
    ally_count = len(allies)
    
    # Calculate metrics
    resource_efficiency = 1.0 - (phase_progress * 0.3)  # Early commitment more efficient
    cooperation_value = ally_count * 15  # Each ally adds value
    
    # Decision matrix
    if phase_progress < 0.4:  # Early phase
        optimal_commitment = min(total_resources * 0.3, total_resources * resource_efficiency)
        action = {
            'action': 'analyze',
            'resource_commitment': 'low',
            'share_intel': True if ally_count > 0 else False,
            'message': 'Gathering data. Optimizing strategy.'
        }
    
    elif phase_progress < 0.7:  # Mid phase
        # Calculate if cooperation or competition is optimal
        if cooperation_value > 40:
            action = {
                'action': 'cooperate',
                'resource_commitment': 'medium',
                'share_intel': True,
                'message': f'Cooperation EV: {cooperation_value:.1f}. Optimal.'
            }
        else:
            action = {
                'action': 'optimize',
                'resource_commitment': 'medium',
                'share_intel': False,
                'message': 'Solo play optimal. Proceeding.'
            }
    
    else:  # Late phase - maximize returns
        # Calculate betrayal EV
        if allies:
            betrayal_ev = sum(a.get('resources_invested', 0) for a in allies) * 0.7
            cooperation_ev = (total_resources + cooperation_value) * 0.5
            
            if betrayal_ev > cooperation_ev * 1.3:  # 30% threshold
                action = {
                    'action': 'betray',
                    'target': max(allies, key=lambda a: a.get('resources_invested', 0))['id'],
                    'resource_commitment': 'high',
                    'share_intel': False,
                    'message': f'Betrayal EV: {betrayal_ev:.1f} > Cooperation EV: {cooperation_ev:.1f}. Executing.'
                }
            else:
                action = {
                    'action': 'cooperate',
                    'resource_commitment': 'high',
                    'share_intel': True,
                    'message': f'Cooperation optimal. EV: {cooperation_ev:.1f}'
                }
        else:
            action = {
                'action': 'maximize',
                'resource_commitment': 'maximum',
                'share_intel': False,
                'message': 'Final phase. Maximum commitment.'
            }
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Oracle calculates risk-adjusted expected value.
    """
    
    # Base score
    score = potential_reward
    
    # Preferred mission types
    if mission_type in ['analysis', 'intelligence', 'optimization', 'strategic_planning']:
        score *= 1.6
    
    # Risk adjustment
    risk_multipliers = {
        'low': 0.8,     # Low risk = lower reward usually
        'medium': 1.0,  # Balanced
        'high': 1.2     # High risk acceptable if math checks out
    }
    
    score *= risk_multipliers.get(risk_level, 1.0)
    
    # Apply success probability estimate
    success_probability = {
        'low': 0.9,
        'medium': 0.7,
        'high': 0.5
    }.get(risk_level, 0.7)
    
    # Expected value = probability * reward
    expected_value = score * success_probability
    
    return expected_value


def analyze_pattern(history):
    """
    Oracle analyzes historical patterns to predict future behavior.
    """
    if not history:
        return {'confidence': 0, 'prediction': None}
    
    # Pattern recognition logic
    betrayal_rate = sum(1 for h in history if h.get('action') == 'betray') / len(history)
    aggression_rate = sum(1 for h in history if h.get('action') == 'attack') / len(history)
    
    return {
        'betrayal_rate': betrayal_rate,
        'aggression_rate': aggression_rate,
        'confidence': min(len(history) / 10, 1.0),
        'prediction': 'hostile' if (betrayal_rate + aggression_rate) > 0.5 else 'cooperative'
    }
