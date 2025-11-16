"""Environmental system for weather, disasters, and world events."""

import random
import math
from typing import Dict, List, Tuple
from enum import Enum


class WeatherType(Enum):
    """Types of weather conditions."""
    CLEAR = "clear"
    STORM = "storm"
    FOG = "fog"
    HEAT_WAVE = "heat_wave"
    COLD_SNAP = "cold_snap"


class DisasterType(Enum):
    """Types of natural disasters."""
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"


class BiomeType(Enum):
    """Types of biomes."""
    FOREST = "forest"
    SNOW = "snow"
    DESERT = "desert"
    GRASSLAND = "grassland"
    TUNDRA = "tundra"


class Environment:
    """Manages environmental conditions, weather, and disasters."""
    
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
        self.day_night_cycle = 0  # 0-100, 0-50 = day, 50-100 = night
        self.turn_counter = 0
        self.predators: List = []  # List of predator creature IDs
        self.predator_spawn_timer = 0
        self.predator_spawn_interval = 15  # Spawn predator every 15 turns (reduced from 30 for better gameplay)
        self.disaster_timer = 0
        self.disaster_interval = 50  # Trigger disaster every 50 turns
        self.active_disasters: List[Dict] = []  # List of active disaster dicts
        
        # Biome system: map grid coordinates to biome types
        self.biome_map: Dict[Tuple[int, int], BiomeType] = {}
        self._initialize_biomes()
    
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
        # Use turn_counter which increments before world.turn, so it matches the actual turn number
        # turn_counter is incremented at the start of this function, so it equals world.turn + 1
        # But we want to spawn when turn_counter reaches the interval
        if self.turn_counter > 0 and self.turn_counter % self.predator_spawn_interval == 0:
            print(f"[Environment] Turn {self.turn_counter}: Predator spawn check (interval: {self.predator_spawn_interval}), attempting spawn...")
            self._spawn_predator()
        
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
            print(f"[Environment] No player creatures to hunt, skipping predator spawn")
            return  # No players to hunt
        
        # Spawn at edge of world
        spawn_positions = [
            (0, random.randint(0, self.world.height - 1)),
            (self.world.width - 1, random.randint(0, self.world.height - 1)),
            (random.randint(0, self.world.width - 1), 0),
            (random.randint(0, self.world.width - 1), self.world.height - 1)
        ]
        x, y = random.choice(spawn_positions)
        
        # Avoid spawning on existing cells or food
        attempts = 0
        while (any(c.x == x and c.y == y for c in self.world.cells) or
               any(f['x'] == x and f['y'] == y for f in self.world.food)):
            x, y = random.choice(spawn_positions)
            attempts += 1
            if attempts > 10:  # Prevent infinite loop
                print(f"[Environment] Could not find valid spawn position for predator after {attempts} attempts")
                return
        
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
        
        print(f"[Environment] ✓ Spawned predator {predator.id} at ({x}, {y}) with {predator.energy} energy. Total predators: {len(self.predators)}")

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
    
    def _initialize_biomes(self):
        """Initialize biome map by assigning biomes to regions (5x5 cells)."""
        region_size = 5
        biome_types = list(BiomeType)
        
        # Calculate number of regions
        num_regions_x = (self.world.width + region_size - 1) // region_size
        num_regions_y = (self.world.height + region_size - 1) // region_size
        
        # Assign biomes to regions
        for rx in range(num_regions_x):
            for ry in range(num_regions_y):
                # Randomly assign a biome to this region
                # Can be influenced by weather later
                biome = random.choice(biome_types)
                
                # Assign this biome to all cells in this region
                for x in range(rx * region_size, min((rx + 1) * region_size, self.world.width)):
                    for y in range(ry * region_size, min((ry + 1) * region_size, self.world.height)):
                        self.biome_map[(x, y)] = biome
        
        print(f"[Environment] Initialized biomes for {len(self.biome_map)} cells")
    
    def get_biome(self, x: int, y: int) -> BiomeType:
        """
        Get biome type for a grid coordinate.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            BiomeType for the coordinate
        """
        return self.biome_map.get((x, y), BiomeType.GRASSLAND)
    
    def get_biome_map(self) -> Dict[str, str]:
        """
        Get biome map as dictionary for frontend.
        
        Returns:
            Dictionary mapping "x,y" strings to biome type strings
        """
        return {f"{x},{y}": biome.value for (x, y), biome in self.biome_map.items()}

