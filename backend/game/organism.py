"""Organism class for Stage 3 evolution."""

import random
from .creature import Creature


class Organism(Creature):
    """Stage 3: Complex organism with specialized parts."""
    
    def __init__(self, creature_id, traits, x, y, player_id=None):
        """
        Initialize an organism.
        
        Args:
            creature_id: Unique identifier
            traits: Dict with color, speed, diet, etc.
            x: Initial x position
            y: Initial y position
            player_id: Player ID (1 or 2) that owns this creature
        """
        super().__init__(creature_id, traits, x, y, stage=3, player_id=player_id)
        
        # Generate specialized parts from traits
        self.parts = self._generate_parts(traits)
        
        # Apply part bonuses
        self._apply_part_bonuses()
    
    def _generate_parts(self, traits):
        """
        Generate organism parts based on traits.
        
        Args:
            traits: Original creature traits
            
        Returns:
            Dict with parts: mouth, limbs, sensors, defense
        """
        diet = traits.get('diet', 'omnivore')
        speed = traits.get('speed', 3)
        
        # Mouth type based on diet
        if diet == 'carnivore':
            mouth = 'sharp'
        elif diet == 'herbivore':
            mouth = 'grinding'
        else:
            mouth = 'versatile'
        
        # Limbs based on speed
        if speed >= 4:
            limbs = random.randint(4, 6)  # Fast = more limbs
        elif speed <= 2:
            limbs = random.randint(2, 3)  # Slow = fewer limbs
        else:
            limbs = random.randint(3, 4)
        
        # Sensors (detection radius)
        sensors = random.randint(2, 5)
        
        # Defense
        defense_types = ['armor', 'spikes', 'camouflage', 'none']
        defense = random.choice(defense_types)
        
        return {
            'mouth': mouth,
            'limbs': limbs,
            'sensors': sensors,
            'defense': defense
        }
    
    def _apply_part_bonuses(self):
        """Apply part bonuses to creature stats."""
        # Limbs affect speed
        limb_bonus = (self.parts['limbs'] - 3) * 0.5  # +0.5 per limb over 3
        self.speed = min(5, self.speed + limb_bonus)
        
        # Sensors affect detection (handled in get_nearby)
        # Defense affects damage reduction (handled in combat)
    
    def get_detection_radius(self):
        """Get detection radius based on sensors."""
        return 3 + self.parts['sensors']  # Base 3 + sensor bonus
    
    def get_defense_value(self):
        """Get defense value for damage reduction."""
        defense_map = {
            'armor': 0.5,  # 50% damage reduction
            'spikes': 0.3,  # 30% damage reduction
            'camouflage': 0.2,  # 20% damage reduction
            'none': 0.0
        }
        return defense_map.get(self.parts['defense'], 0.0)
    
    def to_dict(self):
        """Serialize organism state for frontend."""
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
            'parts': self.parts.copy(),
            'sprite_url': getattr(self, 'sprite_url', None),
            'custom_actions': self.traits.get('custom_actions', [])
        }

