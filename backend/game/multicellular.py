"""Multicellular class for Stage 2 evolution."""

import math
from .creature import Creature


class Colony:
    """Represents a colony of cells."""
    
    def __init__(self, colony_id):
        """Initialize a colony."""
        self.id = colony_id
        self.members = []  # List of Cell objects
        self.shared_energy = 0
    
    def add_member(self, cell):
        """Add a cell to the colony."""
        if cell not in self.members:
            self.members.append(cell)
            self.shared_energy += cell.energy
            cell.colony = self
    
    def remove_member(self, cell):
        """Remove a cell from the colony."""
        if cell in self.members:
            self.members.remove(cell)
            if hasattr(cell, 'colony'):
                del cell.colony
    
    def get_centroid(self):
        """Calculate centroid position of colony."""
        if not self.members:
            return (0, 0)
        x_sum = sum(c.x for c in self.members)
        y_sum = sum(c.y for c in self.members)
        return (x_sum // len(self.members), y_sum // len(self.members))
    
    def get_total_energy(self):
        """Get total energy of colony."""
        return sum(c.energy for c in self.members) + self.shared_energy
    
    def distribute_energy(self):
        """Distribute shared energy evenly among members."""
        if not self.members:
            return
        energy_per_member = self.shared_energy // len(self.members)
        for cell in self.members:
            cell.energy += energy_per_member
        self.shared_energy = 0


class Multicellular(Creature):
    """Stage 2: Multicellular organism (colony of cells)."""
    
    def __init__(self, creature_id, traits, x, y, player_id=None, colony=None):
        """
        Initialize a multicellular creature.
        
        Args:
            creature_id: Unique identifier
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
            player_id: Player ID (1 or 2) that owns this creature
            colony: Optional Colony object to join
        """
        super().__init__(creature_id, traits, x, y, stage=2, player_id=player_id)
        self.colony = colony
        if colony:
            colony.add_member(self)
        else:
            # Create new colony
            self.colony = Colony(creature_id)
            self.colony.add_member(self)
    
    def to_dict(self):
        """Serialize multicellular state for frontend."""
        colony_size = len(self.colony.members) if self.colony else 1
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
            'stage': self.stage,
            'player_id': self.player_id,
            'colony_id': self.colony.id if self.colony else None,
            'colony_size': colony_size,
            'sprite_url': getattr(self, 'sprite_url', None),
            'custom_actions': self.traits.get('custom_actions', [])
        }
    
    def get_position(self):
        """Get position (centroid if in colony, else own position)."""
        # For now, use own position (colony members move together but keep individual positions)
        # In future, could implement true colony movement
        return (self.x, self.y)

