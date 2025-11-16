"""Scoring system for multi-metric tracking and achievements."""

from typing import Dict, List, Optional
from collections import defaultdict


class Achievement:
    """Represents an achievement."""
    
    def __init__(self, name: str, description: str, condition_func):
        """
        Initialize an achievement.
        
        Args:
            name: Achievement name
            description: Achievement description
            condition_func: Function that takes stats and returns True if achieved
        """
        self.name = name
        self.description = description
        self.condition_func = condition_func
        self.unlocked = False
    
    def check(self, stats: Dict) -> bool:
        """
        Check if achievement is unlocked.
        
        Args:
            stats: Statistics dict
            
        Returns:
            True if unlocked
        """
        if not self.unlocked:
            self.unlocked = self.condition_func(stats)
        return self.unlocked


class ScoringSystem:
    """Tracks multi-metric scoring and achievements."""
    
    def __init__(self):
        """Initialize scoring system."""
        self.metrics = {
            'total_energy_gained': 0,
            'total_energy_lost': 0,
            'energy_efficiency': 0.0,  # energy_gained / energy_lost
            'reproduction_count': 0,
            'reproduction_rate': 0.0,  # reproductions per turn
            'combat_kills': 0,
            'combat_deaths': 0,
            'food_consumed': 0,
            'territories_claimed': 0,
            'cooperation_events': 0,
            'migration_count': 0,
            'survival_turns': 0,
            'max_population': 0,
            'evolution_stage': 1
        }
        
        self.achievements = self._initialize_achievements()
        self.turn_history = []  # Track metrics over time
    
    def _initialize_achievements(self) -> List[Achievement]:
        """Initialize achievement list."""
        achievements = []
        
        # Survival achievements
        achievements.append(Achievement(
            "Survivor",
            "Survive 100 turns",
            lambda s: s.get('survival_turns', 0) >= 100
        ))
        
        achievements.append(Achievement(
            "Long Lived",
            "Survive 500 turns",
            lambda s: s.get('survival_turns', 0) >= 500
        ))
        
        # Reproduction achievements
        achievements.append(Achievement(
            "Prolific",
            "Reproduce 10 times",
            lambda s: s.get('reproduction_count', 0) >= 10
        ))
        
        achievements.append(Achievement(
            "Population Boom",
            "Reach population of 20",
            lambda s: s.get('max_population', 0) >= 20
        ))
        
        # Combat achievements
        achievements.append(Achievement(
            "Hunter",
            "Kill 5 enemies",
            lambda s: s.get('combat_kills', 0) >= 5
        ))
        
        achievements.append(Achievement(
            "Predator",
            "Kill 20 enemies",
            lambda s: s.get('combat_kills', 0) >= 20
        ))
        
        # Efficiency achievements
        achievements.append(Achievement(
            "Efficient",
            "Achieve energy efficiency > 2.0",
            lambda s: s.get('energy_efficiency', 0) > 2.0
        ))
        
        # Social achievements
        achievements.append(Achievement(
            "Cooperative",
            "Cooperate 10 times",
            lambda s: s.get('cooperation_events', 0) >= 10
        ))
        
        achievements.append(Achievement(
            "Territorial",
            "Claim 5 territories",
            lambda s: s.get('territories_claimed', 0) >= 5
        ))
        
        # Evolution achievements
        achievements.append(Achievement(
            "Evolved",
            "Reach stage 2",
            lambda s: s.get('evolution_stage', 1) >= 2
        ))
        
        achievements.append(Achievement(
            "Advanced",
            "Reach stage 3",
            lambda s: s.get('evolution_stage', 1) >= 3
        ))
        
        return achievements
    
    def record_event(self, event_type: str, value: int = 1):
        """
        Record an event for scoring.
        
        Args:
            event_type: Type of event
            value: Value to add (default: 1)
        """
        if event_type in self.metrics:
            self.metrics[event_type] += value
        elif event_type == 'energy_gained':
            self.metrics['total_energy_gained'] += value
        elif event_type == 'energy_lost':
            self.metrics['total_energy_lost'] += value
    
    def update_turn(self, turn_number: int, population: int):
        """
        Update turn-based metrics.
        
        Args:
            turn_number: Current turn number
            population: Current population size
        """
        self.metrics['survival_turns'] = turn_number
        self.metrics['max_population'] = max(self.metrics['max_population'], population)
        
        # Calculate efficiency
        if self.metrics['total_energy_lost'] > 0:
            self.metrics['energy_efficiency'] = (
                self.metrics['total_energy_gained'] / self.metrics['total_energy_lost']
            )
        
        # Calculate reproduction rate
        if turn_number > 0:
            self.metrics['reproduction_rate'] = self.metrics['reproduction_count'] / turn_number
        
        # Check achievements
        new_achievements = []
        for achievement in self.achievements:
            if achievement.check(self.metrics) and not achievement.unlocked:
                new_achievements.append(achievement.name)
                achievement.unlocked = True
        
        return new_achievements
    
    def get_score_summary(self) -> Dict:
        """
        Get summary of all scores.
        
        Returns:
            Dict with all metrics and unlocked achievements
        """
        unlocked = [a.name for a in self.achievements if a.unlocked]
        
        return {
            'metrics': self.metrics.copy(),
            'unlocked_achievements': unlocked,
            'total_achievements': len(self.achievements),
            'achievement_progress': len(unlocked) / len(self.achievements) if self.achievements else 0.0
        }

