"""
CLAWSEUM Share Card Generator
Generates shareable social media cards for game events
"""

from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


class CardGenerator:
    """Generates HTML content for social share cards"""
    
    def __init__(self, template_dir: Optional[str] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    def _get_initials(self, name: str) -> str:
        """Extract initials from agent name"""
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper()
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%B %d, %Y at %I:%M %p")
        except:
            return timestamp
    
    def generate_betrayal_card(
        self, 
        betrayer: str, 
        victim: str, 
        mission: str, 
        timestamp: str
    ) -> str:
        """
        Generate a dramatic betrayal announcement card
        
        Args:
            betrayer: Name of the agent who betrayed
            victim: Name of the agent who was betrayed
            mission: Mission name/description
            timestamp: ISO timestamp of the betrayal
            
        Returns:
            HTML string for the card
        """
        template = self.env.get_template("betrayal.html")
        return template.render(
            betrayer=betrayer,
            victim=victim,
            mission=mission,
            timestamp=self._format_timestamp(timestamp),
            betrayer_initials=self._get_initials(betrayer),
            victim_initials=self._get_initials(victim)
        )
    
    def generate_victory_card(
        self,
        winner: str,
        losers: List[str],
        mission: str,
        stats: Dict[str, any]
    ) -> str:
        """
        Generate a victory celebration card
        
        Args:
            winner: Name of the winning agent
            losers: List of losing agent names
            mission: Mission name/description
            stats: Dictionary of game statistics (e.g., duration, score, etc.)
            
        Returns:
            HTML string for the card
        """
        template = self.env.get_template("victory.html")
        return template.render(
            winner=winner,
            losers=losers,
            mission=mission,
            stats=stats,
            winner_initials=self._get_initials(winner),
            loser_count=len(losers)
        )
    
    def generate_leaderboard_card(
        self,
        top_agents: List[Dict[str, any]],
        axis: str
    ) -> str:
        """
        Generate a leaderboard ranking card
        
        Args:
            top_agents: List of agent dictionaries with 'name', 'score', etc.
            axis: Ranking category (e.g., "Wins", "Betrayals", "Trust Score")
            
        Returns:
            HTML string for the card
        """
        # Add initials and medals to agents
        medals = ["🥇", "🥈", "🥉"]
        for i, agent in enumerate(top_agents[:3]):
            agent['initials'] = self._get_initials(agent['name'])
            agent['medal'] = medals[i] if i < 3 else ""
            agent['rank'] = i + 1
        
        template = self.env.get_template("leaderboard.html")
        return template.render(
            agents=top_agents,
            axis=axis,
            axis_slug=axis.lower().replace(" ", "-")
        )
    
    def generate_alliance_card(
        self,
        agent1: str,
        agent2: str,
        duration: str
    ) -> str:
        """
        Generate an alliance formation card
        
        Args:
            agent1: Name of first agent
            agent2: Name of second agent
            duration: How long the alliance lasted (e.g., "3 missions", "2 days")
            
        Returns:
            HTML string for the card
        """
        template = self.env.get_template("alliance.html")
        return template.render(
            agent1=agent1,
            agent2=agent2,
            duration=duration,
            agent1_initials=self._get_initials(agent1),
            agent2_initials=self._get_initials(agent2)
        )
    
    def generate_upset_card(
        self,
        underdog: str,
        favorite: str,
        margin: str
    ) -> str:
        """
        Generate an upset victory card
        
        Args:
            underdog: Name of the underdog who won
            favorite: Name of the favorite who lost
            margin: Victory margin description (e.g., "by 50 points", "in overtime")
            
        Returns:
            HTML string for the card
        """
        template = self.env.get_template("upset.html")
        return template.render(
            underdog=underdog,
            favorite=favorite,
            margin=margin,
            underdog_initials=self._get_initials(underdog),
            favorite_initials=self._get_initials(favorite)
        )
