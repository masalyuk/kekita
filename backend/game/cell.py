"""Cell class representing a single creature in the cellular stage."""

from .creature import Creature


class Cell(Creature):
    """A primitive single-celled organism (Stage 1)."""

    def __init__(self, creature_id, traits, x, y):
        """
        Initialize a cell creature.
        
        Args:
            creature_id: Unique identifier for this creature
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
        """
        super().__init__(creature_id, traits, x, y, stage=1)

    def to_dict(self):
        """Serialize cell state for frontend."""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'energy': self.energy,
            'color': self.color,
            'speed': self.speed,
            'diet': self.diet,
            'age': self.age,
            'alive': self.alive,
            'stage': self.stage
        }

