"""Base Creature class for all evolution stages."""

from abc import ABC, abstractmethod
from .creature_memory import CreatureMemory


class Creature(ABC):
    """Base class for all creatures across evolution stages."""
    
    def __init__(self, creature_id, traits, x, y, stage=1):
        """
        Initialize a creature.
        
        Args:
            creature_id: Unique identifier
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
            stage: Evolution stage (1, 2, or 3)
        """
        self.id = creature_id
        self.color = traits.get('color', 'blue')
        self.speed = traits.get('speed', 3)
        self.diet = traits.get('diet', 'omnivore')
        self.x = x
        self.y = y
        self.energy = 100
        self.age = 0
        self.alive = True
        self.memory = CreatureMemory(max_events=10)
        self.stage = stage
        self.traits = traits  # Store original traits
    
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

