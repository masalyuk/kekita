"""Base Creature class for all evolution stages."""

import random
from abc import ABC, abstractmethod


class Creature(ABC):
    """Base class for all creatures across evolution stages."""
    
    # Food types available in the world
    FOOD_TYPES = ['apple', 'banana', 'grapes']
    
    def __init__(self, creature_id, traits, x, y, stage=1, player_id=None):
        """
        Initialize a creature.
        
        Args:
            creature_id: Unique identifier
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
            stage: Evolution stage (1, 2, or 3)
            player_id: Player ID (1 or 2) that owns this creature
        """
        self.id = creature_id
        self.player_id = player_id
        # Ensure color is a lowercase string
        color = traits.get('color', 'blue')
        self.color = str(color).lower().strip() if color else 'blue'
        self.speed = traits.get('speed', 3)
        self.diet = traits.get('diet', 'omnivore')
        self.x = x
        self.y = y
        self.energy = 100
        self.age = 0
        self.alive = True
        self.stage = stage
        self.traits = traits  # Store original traits
        self.shelter_id = None  # Track which shelter creature is hiding in (None when not hiding)
    
    @abstractmethod
    def to_dict(self):
        """Serialize creature state for frontend."""
        pass
    
    def can_evolve(self) -> bool:
        """
        Check if creature can evolve to next stage.
        
        Returns:
            True if evolution criteria met
        """
        if self.stage == 1:
            # Stage 1 -> Stage 2: energy > 80, age > 10
            return self.energy > 80 and self.age > 10
        elif self.stage == 2:
            # Stage 2 -> Stage 3: energy > 90, age > 20, and colony size >= 3 (if multicellular)
            if hasattr(self, 'colony') and self.colony:
                return self.energy > 90 and self.age > 20 and len(self.colony.members) >= 3
            return False
        return False
    
    def evolve_cost(self) -> int:
        """Energy cost to evolve to next stage."""
        return 50

