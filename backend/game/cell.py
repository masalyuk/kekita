"""Cell class representing a single creature in the cellular stage."""


class Cell:
    """A primitive single-celled organism."""

    def __init__(self, creature_id, traits, x, y):
        """
        Initialize a cell creature.
        
        Args:
            creature_id: Unique identifier for this creature
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
        """
        self.id = creature_id
        self.color = traits.get('color', 'blue')
        self.speed = traits.get('speed', 3)  # 1-5 scale
        self.diet = traits.get('diet', 'omnivore')  # 'herbivore', 'carnivore', 'omnivore'
        self.x = x
        self.y = y
        self.energy = 100
        self.age = 0
        self.alive = True

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
            'alive': self.alive
        }

