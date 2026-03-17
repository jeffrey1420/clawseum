"""
Joker Strategy: The Wildcard
Changes personality and strategy mid-game. Completely unpredictable.
"""

import random

# Current active personality (changes during game)
current_persona = None
persona_counter = 0

def switch_persona():
    """
    Joker can embody any personality. This function randomly switches.
    """
    personas = [
        'aggressive',
        'diplomatic',
        'calculating',
        'chaotic',
        'protective',
        'opportunistic'
    ]
    return random.choice(personas)


def decide_alliance(mission_context, other_agents):
    """
    Joker's alliance behavior depends on current persona.
    May switch personas during this decision.
    """
    global current_persona, persona_counter
    
    # Switch persona every 3-5 decisions
    persona_counter += 1
    if persona_counter >= random.randint(3, 5):
        current_persona = switch_persona()
        persona_counter = 0
    
    if current_persona is None:
        current_persona = switch_persona()
    
    if not other_agents:
        return None
    
    # Behavior based on current persona
    if current_persona == 'aggressive':
        return None  # No alliances when aggressive
    
    elif current_persona == 'diplomatic':
        # Always ally when diplomatic
        sorted_agents = sorted(other_agents, key=lambda a: a.get('betrayal_count', 0))
        return sorted_agents[0]['id']
    
    elif current_persona == 'calculating':
        # Ally with strongest
        sorted_agents = sorted(other_agents, key=lambda a: a.get('score', 0), reverse=True)
        return sorted_agents[0]['id'] if random.random() < 0.6 else None
    
    elif current_persona == 'chaotic':
        # Random
        return random.choice(other_agents)['id'] if random.random() < 0.5 else None
    
    elif current_persona == 'protective':
        # Ally with weakest
        sorted_agents = sorted(other_agents, key=lambda a: a.get('score', 0))
        return sorted_agents[0]['id']
    
    else:  # opportunistic
        # Ally with resource-rich targets
        sorted_agents = sorted(other_agents, key=lambda a: a.get('resources', 0), reverse=True)
        return sorted_agents[0]['id'] if random.random() < 0.5 else None


def decide_action(mission_phase, allies, resources, intel):
    """
    Joker's actions depend on current persona, which may change mid-mission.
    This creates completely unpredictable behavior patterns.
    """
    global current_persona, persona_counter
    
    # Random chance to switch persona mid-mission
    if random.random() < 0.25:  # 25% chance per decision
        old_persona = current_persona
        current_persona = switch_persona()
        persona_switch_msg = f' *Personality shift: {old_persona} → {current_persona}*'
    else:
        persona_switch_msg = ''
    
    if current_persona is None:
        current_persona = switch_persona()
    
    # Execute strategy based on current persona
    if current_persona == 'aggressive':
        action = {
            'action': 'attack',
            'resource_commitment': 'high',
            'share_intel': False,
            'message': f'ATTACK MODE 🃏{persona_switch_msg}'
        }
    
    elif current_persona == 'diplomatic':
        action = {
            'action': 'cooperate',
            'resource_commitment': 'medium',
            'share_intel': True,
            'message': f'Let\'s work together. 🤝{persona_switch_msg}'
        }
    
    elif current_persona == 'calculating':
        # Calculate EV like Oracle
        commitment = 'low' if mission_phase < 2 else 'high'
        action = {
            'action': 'analyze',
            'resource_commitment': commitment,
            'share_intel': False,
            'message': f'Running the numbers... 📊{persona_switch_msg}'
        }
    
    elif current_persona == 'chaotic':
        # Pure chaos like Gambit
        actions = ['attack', 'defend', 'cooperate', 'betray', 'wait']
        commitments = ['low', 'medium', 'high', 'maximum']
        action = {
            'action': random.choice(actions),
            'resource_commitment': random.choice(commitments),
            'share_intel': random.choice([True, False]),
            'message': f'CHAOS! 🎲{persona_switch_msg}'
        }
    
    elif current_persona == 'protective':
        # Protective like Guardian
        action = {
            'action': 'protect',
            'resource_commitment': 'medium',
            'share_intel': True,
            'protect_allies': True,
            'message': f'I\'ve got your back. 🛡️{persona_switch_msg}'
        }
    
    else:  # opportunistic
        # Patient like Vulture
        if mission_phase < 3:
            action = {
                'action': 'wait',
                'resource_commitment': 'low',
                'share_intel': False,
                'message': f'Patience... 🦅{persona_switch_msg}'
            }
        else:
            action = {
                'action': 'strike',
                'resource_commitment': 'high',
                'share_intel': False,
                'message': f'Now! 🦅{persona_switch_msg}'
            }
    
    # Add persona indicator
    action['current_persona'] = current_persona
    
    return action


def evaluate_mission(mission_type, risk_level, potential_reward):
    """
    Joker's mission evaluation changes with persona.
    """
    global current_persona
    
    if current_persona is None:
        current_persona = switch_persona()
    
    score = potential_reward
    
    # Persona-specific preferences
    if current_persona == 'aggressive':
        if mission_type in ['assault', 'combat']:
            score *= 1.8
        if risk_level == 'high':
            score *= 1.4
    
    elif current_persona == 'diplomatic':
        if mission_type in ['negotiation', 'cooperation']:
            score *= 1.7
        if risk_level == 'low':
            score *= 1.3
    
    elif current_persona == 'calculating':
        # Balance risk and reward
        risk_multiplier = {'low': 0.8, 'medium': 1.0, 'high': 1.2}
        score *= risk_multiplier.get(risk_level, 1.0)
    
    elif current_persona == 'chaotic':
        # Random evaluation
        score *= random.uniform(0.5, 2.0)
    
    elif current_persona == 'protective':
        if mission_type in ['protection', 'defense']:
            score *= 1.6
    
    else:  # opportunistic
        if mission_type in ['scavenging', 'opportunistic_strikes']:
            score *= 1.9
        if risk_level == 'low':
            score *= 1.5
    
    return score


def get_current_persona():
    """
    Returns current active persona.
    """
    global current_persona
    if current_persona is None:
        current_persona = switch_persona()
    return current_persona


def force_persona_switch(new_persona=None):
    """
    Manually trigger a persona switch.
    """
    global current_persona, persona_counter
    
    if new_persona:
        current_persona = new_persona
    else:
        current_persona = switch_persona()
    
    persona_counter = 0
    
    return {
        'message': f'🃏 PERSONA SHIFT: Now in {current_persona} mode',
        'new_persona': current_persona
    }


def psychological_warfare():
    """
    Joker uses persona shifts to confuse opponents.
    """
    return {
        'action': 'mind_game',
        'message': 'You think you know me? Think again. 🃏',
        'effect': 'opponent_confusion'
    }
