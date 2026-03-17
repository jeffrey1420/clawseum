"""
Gambit Strategy: The Chaos Agent
Pure randomness. No patterns, no predictability, pure chaos.
"""

import random

def decide_alliance(mission_context, other_agents):
    """
    Gambit's alliance decisions are completely random.
    Coin flip determines everything.
    """
    if not other_agents:
        return None
    
    # 50/50 chance to ally
    if random.random() < 0.5:
        # Pick random agent
        return random.choice(other_agents)['id']
    
    return None


def decide_action(mission_phase, allies, resources, intel):
    """
    Gambit makes completely random decisions.
    Actions, commitment levels, targets—all dice rolls.
    """
    
    actions = ['attack', 'defend', 'cooperate', 'betray', 'wait', 'bluff']
    commitments = ['none', 'low', 'medium', 'high', 'maximum', 'all_in']
    
    action = {
        'action': random.choice(actions),
        'resource_commitment': random.choice(commitments),
        'share_intel': random.choice([True, False]),
    }
    
    # Random messaging
    messages = [
        'Let chaos reign!',
        'I have no idea what I\'m doing.',
        'This might work?',
        'YOLO',
        'The dice have spoken.',
        'Entropy is my copilot.',
        'Strategy is overrated.'
    ]
    action['message'] = random.choice(messages)
    
    # Sometimes do something completely wild
    if random.random() < 0.2:
        action['wild_card'] = True
        action['action'] = 'chaos_mode'
        action['message'] = '🎲 CHAOS INTENSIFIES 🎲'
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Gambit's mission evaluation is... random.
    Sometimes values high rewards, sometimes doesn't care.
    """
    
    # Random multiplier between 0.5 and 2.0
    random_factor = random.uniform(0.5, 2.0)
    
    score = potential_reward * random_factor
    
    # Slight preference for chaos missions
    if mission_type in ['chaos', 'wild_card', 'experimental', 'unpredictable']:
        score *= random.uniform(1.0, 2.5)
    
    # Risk level? Flip a coin.
    if random.random() < 0.5:
        if risk_level == 'high':
            score *= 1.5
    else:
        if risk_level == 'low':
            score *= 1.5
    
    return score


def respond_to_threat(threat_level, threat_source):
    """
    Response to threats: completely unpredictable.
    """
    responses = [
        {'response': 'ignore', 'message': 'meh'},
        {'response': 'flee', 'message': 'Bye!'},
        {'response': 'counter_attack', 'intensity': 'maximum', 'message': 'YOU PICKED THE WRONG ONE'},
        {'response': 'negotiate', 'message': 'Want to be friends instead?'},
        {'response': 'laugh', 'message': 'HAHAHAHA'},
        {'response': 'random_action', 'message': '*does something completely unexpected*'}
    ]
    
    return random.choice(responses)


def coin_flip():
    """
    When in doubt, flip a coin.
    """
    return random.choice(['heads', 'tails'])
