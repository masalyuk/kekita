"""Environmental system for hazards, weather, and world events."""

import random
import math
from typing import Dict, List, Tuple, Optional
from enum import Enum


class WeatherType(Enum):
    """Types of weather conditions."""
    CLEAR = "clear"
    STORM = "storm"
    FOG = "fog"
    HEAT_WAVE = "heat_wave"
    COLD_SNAP = "cold_snap"


class HazardType(Enum):
    """Types of environmental hazards."""
    POISON_ZONE = "poison_zone"
    DANGEROUS_AREA = "dangerous_area"
    PREDATOR = "predator"


class DisasterType(Enum):
    """Types of natural disasters."""
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"


class Environment:
    """Manages environmental conditions and hazards."""
    
    def __init__(self, world):
        """
        Initialize environment system.
        
        Args:
            world: World instance
        """
        self.world = world
        self.weather: WeatherType = WeatherType.CLEAR
        self.weather_duration = 0
        self.weather_change_turn = 0
        self.hazards: List[Dict] = []  # List of hazard dicts
        self.day_night_cycle = 0  # 0-100, 0-50 = day, 50-100 = night
        self.turn_counter = 0
        self.predators: List = []  # List of predator creature IDs
        self.predator_spawn_timer = 0
        self.predator_spawn_interval = 30  # Spawn predator every 30 turns
        self.disaster_timer = 0
        self.disaster_interval = 50  # Trigger disaster every 50 turns
        self.active_disasters: List[Dict] = []  # List of active disaster dicts
        
        # Initialize some hazards
        self._spawn_hazards()
    
    def _spawn_hazards(self, num_poison_zones=2, num_dangerous_areas=1):
        """Spawn initial environmental hazards."""
        for _ in range(num_poison_zones):
            x = random.randint(0, self.world.width - 1)
            y = random.randint(0, self.world.height - 1)
            radius = random.randint(2, 4)
            self.hazards.append({
                'type': HazardType.POISON_ZONE,
                'x': x,
                'y': y,
                'radius': radius,
                'damage_per_turn': 5
            })
        
        for _ in range(num_dangerous_areas):
            x = random.randint(0, self.world.width - 1)
            y = random.randint(0, self.world.height - 1)
            radius = random.randint(1, 3)
            self.hazards.append({
                'type': HazardType.DANGEROUS_AREA,
                'x': x,
                'y': y,
                'radius': radius,
                'damage_per_turn': 3
            })
    
    def update(self):
        """Update environmental conditions each turn."""
        self.turn_counter += 1
        
        # Update day/night cycle (10 turns = full cycle)
        self.day_night_cycle = (self.turn_counter * 10) % 100
        
        # Update weather (changes every 20 turns)
        if self.turn_counter - self.weather_change_turn >= 20:
            self._change_weather()
            self.weather_change_turn = self.turn_counter
        
        # Spawn predators periodically
        self.predator_spawn_timer += 1
        if self.predator_spawn_timer >= self.predator_spawn_interval:
            self._spawn_predator()
            self.predator_spawn_timer = 0
        
        # Update predator AI
        self._update_predators()
        
        # Trigger natural disasters periodically
        self.disaster_timer += 1
        if self.disaster_timer >= self.disaster_interval:
            self._trigger_disaster()
            self.disaster_timer = 0
        
        # Update active disasters
        self._update_disasters()
        
        # Apply weather effects to creatures
        self._apply_weather_effects()
        
        # Apply hazard effects
        self._apply_hazard_effects()
    
    def _change_weather(self):
        """Change weather condition randomly."""
        weathers = list(WeatherType)
        self.weather = random.choice(weathers)
        self.weather_duration = random.randint(10, 30)
        print(f"[Environment] Weather changed to {self.weather.value}")
    
    def _apply_weather_effects(self):
        """Apply weather effects to creatures."""
        if self.weather == WeatherType.STORM:
            # Storms reduce movement speed and visibility
            for creature in self.world.cells:
                if creature.alive:
                    # Slight energy drain in storms
                    creature.energy = max(0, creature.energy - 1)
        elif self.weather == WeatherType.HEAT_WAVE:
            # Heat waves increase energy consumption
            for creature in self.world.cells:
                if creature.alive:
                    creature.energy = max(0, creature.energy - 2)
        elif self.weather == WeatherType.COLD_SNAP:
            # Cold snaps slow movement
            for creature in self.world.cells:
                if creature.alive:
                    creature.energy = max(0, creature.energy - 1)
        elif self.weather == WeatherType.FOG:
            # Fog reduces detection radius (handled in get_nearby)
            pass
    
    def _apply_hazard_effects(self):
        """Apply hazard effects to creatures in hazard zones."""
        for hazard in self.hazards:
            for creature in self.world.cells:
                if not creature.alive:
                    continue
                
                distance = math.sqrt((creature.x - hazard['x'])**2 + (creature.y - hazard['y'])**2)
                if distance <= hazard['radius']:
                    # Creature is in hazard zone
                    damage = hazard['damage_per_turn']
                    creature.energy = max(0, creature.energy - damage)
    
    def is_in_hazard(self, x: int, y: int) -> Tuple[bool, Optional[HazardType]]:
        """
        Check if position is in a hazard zone.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Tuple of (is_in_hazard, hazard_type)
        """
        for hazard in self.hazards:
            distance = math.sqrt((x - hazard['x'])**2 + (y - hazard['y'])**2)
            if distance <= hazard['radius']:
                return True, hazard['type']
        return False, None
    
    def is_day(self) -> bool:
        """Check if it's currently day time."""
        return self.day_night_cycle < 50
    
    def get_visibility_modifier(self) -> float:
        """
        Get visibility modifier based on weather and time.
        
        Returns:
            Visibility multiplier (1.0 = full visibility, 0.5 = reduced)
        """
        modifier = 1.0
        
        if not self.is_day():
            modifier *= 0.7  # Night reduces visibility
        
        if self.weather == WeatherType.FOG:
            modifier *= 0.5  # Fog reduces visibility
        
        return modifier

    def _spawn_predator(self):
        """Spawn an NPC predator that hunts player creatures."""
        from .cell import Cell
        
        # Find a random position away from player creatures
        player_creatures = [c for c in self.world.cells if c.alive and c.player_id is not None]
        if not player_creatures:
            return  # No players to hunt
        
        # Spawn at edge of world
        spawn_positions = [
            (0, random.randint(0, self.world.height - 1)),
            (self.world.width - 1, random.randint(0, self.world.height - 1)),
            (random.randint(0, self.world.width - 1), 0),
            (random.randint(0, self.world.width - 1), self.world.height - 1)
        ]
        x, y = random.choice(spawn_positions)
        
        # Create predator with aggressive traits
        predator_traits = {
            'color': 'red',
            'speed': 4,  # Fast
            'diet': 'carnivore',
            'aggression': 'high',
            'size': 'medium',
            'social': 'solitary',
            'is_predator': True  # Mark as predator
        }
        
        predator = Cell(
            creature_id=self.world._resource_id_counter,
            traits=predator_traits,
            x=x,
            y=y,
            player_id=None  # NPC, no player
        )
        predator.energy = 80  # Start with high energy
        self.world.add_cell(predator)
        self.world._resource_id_counter += 1
        self.predators.append(predator.id)
        
        print(f"[Environment] Spawned predator {predator.id} at ({x}, {y})")

    def _update_predators(self):
        """Update predator AI - make them hunt player creatures."""
        for predator_id in self.predators[:]:  # Copy list to avoid modification during iteration
            predator = next((c for c in self.world.cells if c.id == predator_id), None)
            if not predator or not predator.alive:
                if predator_id in self.predators:
                    self.predators.remove(predator_id)
                continue
            
            # Find nearest player creature
            player_creatures = [c for c in self.world.cells 
                              if c.alive and c.player_id is not None]
            
            if not player_creatures:
                continue
            
            # Find nearest target
            predator_pos_x, predator_pos_y = predator.x, predator.y
            if hasattr(predator, 'get_position'):
                predator_pos_x, predator_pos_y = predator.get_position()
            
            nearest_target = None
            min_dist = float('inf')
            
            for target in player_creatures:
                target_pos_x, target_pos_y = target.x, target.y
                if hasattr(target, 'get_position'):
                    target_pos_x, target_pos_y = target.get_position()
                
                dist = math.sqrt((target_pos_x - predator_pos_x)**2 + 
                               (target_pos_y - predator_pos_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_target = target
            
            if nearest_target and min_dist <= 1.5:
                # Attack if in range
                if predator.energy >= 50:
                    # Store action for execution in world.update_cells
                    if not hasattr(self.world, '_predator_actions'):
                        self.world._predator_actions = {}
                    self.world._predator_actions[predator.id] = {
                        'action': 'attack',
                        'target_id': nearest_target.id
                    }
            elif nearest_target:
                # Move toward target
                target_pos_x, target_pos_y = nearest_target.x, nearest_target.y
                if hasattr(nearest_target, 'get_position'):
                    target_pos_x, target_pos_y = nearest_target.get_position()
                
                dx = 1 if target_pos_x > predator_pos_x else (-1 if target_pos_x < predator_pos_x else 0)
                dy = 1 if target_pos_y > predator_pos_y else (-1 if target_pos_y < predator_pos_y else 0)
                
                if not hasattr(self.world, '_predator_actions'):
                    self.world._predator_actions = {}
                self.world._predator_actions[predator.id] = {
                    'action': 'move',
                    'direction': (dx, dy)
                }

    def _trigger_disaster(self):
        """Trigger a random natural disaster."""
        disaster_type = random.choice(list(DisasterType))
        
        if disaster_type == DisasterType.EARTHQUAKE:
            self._trigger_earthquake()
        elif disaster_type == DisasterType.FLOOD:
            self._trigger_flood()

    def _trigger_earthquake(self):
        """Trigger an earthquake that damages creatures in an area."""
        # Random epicenter
        epicenter_x = random.randint(0, self.world.width - 1)
        epicenter_y = random.randint(0, self.world.height - 1)
        radius = random.randint(3, 6)
        duration = random.randint(3, 5)  # Lasts 3-5 turns
        
        disaster = {
            'type': DisasterType.EARTHQUAKE,
            'x': epicenter_x,
            'y': epicenter_y,
            'radius': radius,
            'duration': duration,
            'turn': self.turn_counter
        }
        self.active_disasters.append(disaster)
        
        print(f"[Environment] EARTHQUAKE triggered at ({epicenter_x}, {epicenter_y}) with radius {radius}")
        
        # Immediate damage to creatures in area
        for creature in self.world.cells:
            if not creature.alive:
                continue
            
            creature_pos_x, creature_pos_y = creature.x, creature.y
            if hasattr(creature, 'get_position'):
                creature_pos_x, creature_pos_y = creature.get_position()
            
            dist = math.sqrt((creature_pos_x - epicenter_x)**2 + 
                           (creature_pos_y - epicenter_y)**2)
            if dist <= radius:
                # Damage based on distance (closer = more damage)
                damage = int(15 * (1 - dist / radius))
                creature.energy = max(0, creature.energy - damage)
                if creature.energy == 0:
                    creature.alive = False

    def _trigger_flood(self):
        """Trigger a flood that washes away food/resources in an area."""
        # Random flood area
        flood_x = random.randint(0, self.world.width - 1)
        flood_y = random.randint(0, self.world.height - 1)
        radius = random.randint(4, 7)
        duration = random.randint(4, 6)  # Lasts 4-6 turns
        
        disaster = {
            'type': DisasterType.FLOOD,
            'x': flood_x,
            'y': flood_y,
            'radius': radius,
            'duration': duration,
            'turn': self.turn_counter
        }
        self.active_disasters.append(disaster)
        
        print(f"[Environment] FLOOD triggered at ({flood_x}, {flood_y}) with radius {radius}")
        
        # Remove food in flooded area
        food_to_remove = []
        for food in self.world.food:
            dist = math.sqrt((food['x'] - flood_x)**2 + (food['y'] - flood_y)**2)
            if dist <= radius:
                food_to_remove.append(food)
        
        for food in food_to_remove:
            # Remove from spatial index
            self.world.spatial_index.remove_object(food['id'], food['x'], food['y'])
            self.world.food.remove(food)
        
        # Damage creatures in flooded area
        for creature in self.world.cells:
            if not creature.alive:
                continue
            
            creature_pos_x, creature_pos_y = creature.x, creature.y
            if hasattr(creature, 'get_position'):
                creature_pos_x, creature_pos_y = creature.get_position()
            
            dist = math.sqrt((creature_pos_x - flood_x)**2 + 
                           (creature_pos_y - flood_y)**2)
            if dist <= radius:
                # Flood damage
                creature.energy = max(0, creature.energy - 5)
                if creature.energy == 0:
                    creature.alive = False

    def _update_disasters(self):
        """Update active disasters and remove expired ones."""
        expired_disasters = []
        
        for disaster in self.active_disasters:
            elapsed = self.turn_counter - disaster['turn']
            if elapsed >= disaster['duration']:
                expired_disasters.append(disaster)
            else:
                # Apply ongoing effects
                if disaster['type'] == DisasterType.EARTHQUAKE:
                    # Ongoing earthquake damage (less than initial)
                    for creature in self.world.cells:
                        if not creature.alive:
                            continue
                        
                        creature_pos_x, creature_pos_y = creature.x, creature.y
                        if hasattr(creature, 'get_position'):
                            creature_pos_x, creature_pos_y = creature.get_position()
                        
                        dist = math.sqrt((creature_pos_x - disaster['x'])**2 + 
                                       (creature_pos_y - disaster['y'])**2)
                        if dist <= disaster['radius']:
                            # Ongoing minor damage
                            creature.energy = max(0, creature.energy - 2)
                            if creature.energy == 0:
                                creature.alive = False
                
                elif disaster['type'] == DisasterType.FLOOD:
                    # Ongoing flood damage
                    for creature in self.world.cells:
                        if not creature.alive:
                            continue
                        
                        creature_pos_x, creature_pos_y = creature.x, creature.y
                        if hasattr(creature, 'get_position'):
                            creature_pos_x, creature_pos_y = creature.get_position()
                        
                        dist = math.sqrt((creature_pos_x - disaster['x'])**2 + 
                                       (creature_pos_y - disaster['y'])**2)
                        if dist <= disaster['radius']:
                            # Ongoing flood damage
                            creature.energy = max(0, creature.energy - 3)
                            if creature.energy == 0:
                                creature.alive = False
        
        # Remove expired disasters
        for disaster in expired_disasters:
            self.active_disasters.remove(disaster)

