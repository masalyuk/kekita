"""World class managing game state, creatures, and resources."""

import random
import math


class World:
    """2D grid world containing creatures, food, light."""

    # Food types with emoji mappings
    FOOD_TYPES = ['apple', 'banana', 'grapes']
    FOOD_EMOJIS = {
        'apple': '🍎',
        'banana': '🍌',
        'grapes': '🍇'
    }

    def __init__(self, width=20, height=20, food_type_config=None):
        """
        Initialize the world.
        
        Args:
            width: Grid width
            height: Grid height
            food_type_config: Optional dict with food type configuration to reuse.
                            If None, generates a new random configuration.
        """
        self.width = width
        self.height = height
        self.cells = []  # List of Creature objects (Cell, Multicellular, Organism)
        self.food = []   # [{x, y, id, type}, ...]
        self.light = []
        self.turn = 0
        self._resource_id_counter = 1000  # Start IDs high to avoid conflicts
        self.max_stage = 1  # Track highest stage present
        # Track unique energy events per attempt: set of (action, object, energy_change) tuples
        self.energy_events = set()
        
        # Regional food density: divide world into regions with different densities
        # Regions are 5x5 cells by default
        self.region_size = 5
        self.regions = {}  # {(region_x, region_y): density_multiplier}
        self._initialize_regions()
        
        # Resource manager for depletion, competition, regeneration
        from .resource_manager import ResourceManager
        self.resource_manager = ResourceManager(self)
        
        # Territory and social systems
        from .territory import TerritoryManager
        from .social_system import SocialSystem
        from .environment import Environment
        
        self.territory_manager = TerritoryManager(self)
        self.social_system = SocialSystem(self)
        self.environment = Environment(self)
        
        # Spatial index for performance
        from .spatial_index import SpatialIndex
        self.spatial_index = SpatialIndex(width, height, cell_size=5)
        
        # Initialize spatial index with initial state
        # (will be rebuilt each turn after updates)
        
        # Initialize food type configuration
        # If provided, reuse existing config; otherwise generate new random config
        if food_type_config is not None:
            self.food_type_config = food_type_config.copy()  # Use provided config
            print(f"[DEBUG] Food Type Configuration (reused from game start):")
        else:
            # Each food type gets a random base energy value (25-35 range for similarity)
            # One type will be randomly selected as lethal
            # Each type will be randomly assigned as positive (adds energy) or negative (removes energy)
            self.food_type_config = {}
            lethal_type = random.choice(self.FOOD_TYPES)
            
            for food_type in self.FOOD_TYPES:
                base_energy = random.randint(25, 35)
                is_positive = random.choice([True, False])
                is_lethal = (food_type == lethal_type)
                
                self.food_type_config[food_type] = {
                    'base_energy': base_energy,
                    'is_positive': is_positive,
                    'is_lethal': is_lethal
                }
            print(f"[DEBUG] Food Type Configuration (new game):")
        
        # Log the food type configuration
        for food_type, config in self.food_type_config.items():
            effect = "adds" if config['is_positive'] else "removes"
            lethal = " (LETHAL)" if config['is_lethal'] else ""
            print(f"[DEBUG]   {food_type}: base_energy={config['base_energy']}, {effect} energy{lethal}")

    def _initialize_regions(self):
        """Initialize regional food density map with varying densities."""
        num_regions_x = (self.width + self.region_size - 1) // self.region_size
        num_regions_y = (self.height + self.region_size - 1) // self.region_size
        
        # Create regions with random density multipliers (0.3 to 1.5)
        # Lower values = scarce, higher values = abundant
        for rx in range(num_regions_x):
            for ry in range(num_regions_y):
                # Random density between 0.3 (scarce) and 1.5 (abundant)
                density = random.uniform(0.3, 1.5)
                self.regions[(rx, ry)] = density
        
        print(f"[DEBUG] Initialized {num_regions_x * num_regions_y} regions with varying food densities")
    
    def get_region_density(self, x, y):
        """
        Get food density multiplier for a given position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Density multiplier (0.3 to 1.5)
        """
        region_x = x // self.region_size
        region_y = y // self.region_size
        return self.regions.get((region_x, region_y), 1.0)

    def add_cell(self, creature):
        """Add creature to world (works for Cell, Multicellular, Organism)."""
        self.cells.append(creature)
        # Update max stage
        if hasattr(creature, 'stage'):
            self.max_stage = max(self.max_stage, creature.stage)
        # Add to spatial index
        if hasattr(creature, 'get_position'):
            pos_x, pos_y = creature.get_position()
        else:
            pos_x, pos_y = creature.x, creature.y
        self.spatial_index.add_object(creature.id, pos_x, pos_y, 'creature')

    def spawn_resources(self, num_food=50, num_poison=0):
        """
        Generate food items at random positions using type-based configuration.
        Uses regional density to create food scarcity/abundance zones.
        
        Args:
            num_food: Total number of food items to spawn (base amount)
            num_poison: Ignored (kept for compatibility)
        """
        # Calculate total density across all regions for normalization
        total_density = sum(self.regions.values())
        avg_density = total_density / len(self.regions) if self.regions else 1.0
        
        # Spawn food items with regional variation
        spawned_count = 0
        max_attempts = num_food * 3  # Prevent infinite loops
        attempts = 0
        
        while spawned_count < num_food and attempts < max_attempts:
            attempts += 1
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            
            # Avoid spawning on existing cells
            if any(c.x == x and c.y == y for c in self.cells):
                continue
            
            # Get regional density for this position
            region_density = self.get_region_density(x, y)
            
            # Probability of spawning food in this region based on density
            # Higher density = more likely to spawn
            spawn_probability = region_density / avg_density
            
            # Cap probability to avoid too extreme values
            spawn_probability = min(1.0, max(0.1, spawn_probability))
            
            # Roll for spawn
            if random.random() > spawn_probability:
                continue  # Skip this position
            
            # Randomly assign a food type
            food_type = random.choice(self.FOOD_TYPES)
            
            # Get base energy from config and apply ±10% variation
            base_energy = self.food_type_config[food_type]['base_energy']
            energy_value = base_energy * random.uniform(0.9, 1.1)
            
            # Make energy negative if this type removes energy
            if not self.food_type_config[food_type]['is_positive']:
                energy_value = -energy_value
            
            # Round to integer for cleaner values
            energy_value = int(round(energy_value))
            
            food_item = {
                'x': x,
                'y': y,
                'id': self._resource_id_counter,
                'type': food_type,
                'energy_value': energy_value,
                'region_density': region_density  # Store for reference
            }
            self.food.append(food_item)
            # Add to spatial index
            self.spatial_index.add_object(self._resource_id_counter, x, y, 'food')
            self._resource_id_counter += 1
            spawned_count += 1
        
        # Debug logging: print lists of food with their types
        self._debug_log_food_poison()

    def _debug_log_food_poison(self):
        """Print debug logs showing food items with their type properties."""
        print(f"[DEBUG] Food Summary (Total items: {len(self.food)})")
        
        # Group food by type for better readability
        food_by_type = {}
        for food in self.food:
            food_type = food.get('type', 'unknown')
            if food_type not in food_by_type:
                food_by_type[food_type] = []
            food_by_type[food_type].append(food)
        
        for food_type, items in food_by_type.items():
            config = self.food_type_config.get(food_type, {})
            effect = "adds" if config.get('is_positive', True) else "removes"
            lethal = " (LETHAL)" if config.get('is_lethal', False) else ""
            print(f"[DEBUG] {food_type} ({len(items)} items) - {effect} energy{lethal}:")
            for food in items[:5]:  # Show first 5 items of each type
                energy = food.get('energy_value', 0)
                sign = "+" if energy > 0 else ""
                print(f"[DEBUG]   - {food_type} @ ({food['x']}, {food['y']}) ID:{food['id']} energy:{sign}{energy}")
            if len(items) > 5:
                print(f"[DEBUG]   ... and {len(items) - 5} more {food_type} items")

    def get_nearby(self, creature, radius=None):
        """
        Return nearby objects for a creature.
        Uses spatial index for efficient queries.
        
        Args:
            creature: Creature object to check around (Cell, Multicellular, or Organism)
            radius: Search radius (default: 3 for Stage 1-2, larger for Stage 3)
            
        Returns:
            Dict with food, enemy lists, each containing dicts with x, y, dist, id, type
        """
        # Use detection radius for Stage 3 organisms
        if radius is None:
            if hasattr(creature, 'get_detection_radius'):
                radius = creature.get_detection_radius()
            else:
                radius = 3
        nearby = {
            'food': [],
            'enemy': []
        }

        # Get creature position (centroid for multicellular)
        if hasattr(creature, 'get_position'):
            pos_x, pos_y = creature.get_position()
        else:
            pos_x, pos_y = creature.x, creature.y

        # Use spatial index for efficient queries
        # Get nearby food from spatial index
        nearby_food_objs = self.spatial_index.get_nearby(pos_x, pos_y, radius, obj_type='food')
        for food_obj in nearby_food_objs:
            # Find the actual food item to get full details
            food_item = next((f for f in self.food if f['id'] == food_obj['id']), None)
            if food_item:
                nearby['food'].append({
                    'x': food_item['x'],
                    'y': food_item['y'],
                    'id': food_item['id'],
                    'type': food_item.get('type', 'apple'),  # Include type for frontend
                    'dist': food_obj['dist']
                })
        nearby['food'].sort(key=lambda f: f['dist'])

        # Get nearby creatures from spatial index
        nearby_creature_objs = self.spatial_index.get_nearby(pos_x, pos_y, radius, obj_type='creature')
        for creature_obj in nearby_creature_objs:
            # Find the actual creature to get full details
            other_creature = next((c for c in self.cells if c.id == creature_obj['id']), None)
            if other_creature and other_creature.id != creature.id and other_creature.alive:
                # Skip if same colony (multicellular)
                if hasattr(creature, 'colony') and hasattr(other_creature, 'colony'):
                    if creature.colony and other_creature.colony and creature.colony.id == other_creature.colony.id:
                        continue
                
                other_pos_x = other_creature.x
                other_pos_y = other_creature.y
                if hasattr(other_creature, 'get_position'):
                    other_pos_x, other_pos_y = other_creature.get_position()
                
                nearby['enemy'].append({
                    'x': other_pos_x,
                    'y': other_pos_y,
                    'id': other_creature.id,
                    'dist': creature_obj['dist'],
                    'energy': other_creature.energy,
                    'stage': other_creature.stage
                })
        nearby['enemy'].sort(key=lambda e: e['dist'])

        return nearby

    def update_cells(self, actions):
        """
        Execute creature actions, resolve collisions, update energy.
        
        Args:
            actions: Dict mapping cell_id to action dict
                   {'action': 'move', 'direction': (dx, dy)} or
                   {'action': 'eat', 'target_id': id} or
                   {'action': 'flee', 'direction': (dx, dy)} or
                   {'action': 'reproduce'}
        
        Returns:
            Tuple of (string_events, detailed_events)
            - string_events: List of event strings for display
            - detailed_events: List of dicts with detailed event info
        """
        events = []
        detailed_events = []
        
        # Merge predator actions into main actions dict
        if hasattr(self, '_predator_actions'):
            actions.update(self._predator_actions)
            delattr(self, '_predator_actions')

        # Process actions
        for creature in self.cells:
            if not creature.alive:
                continue

            action = actions.get(creature.id)
            if not action:
                print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} has no action")
                continue

            action_type = action.get('action')
            print(f"[DEBUG] Turn {self.turn}: Executing action for Creature {creature.id} (Player {creature.player_id}): {action_type} - {action}")
            
            # Get position (centroid for multicellular)
            if hasattr(creature, 'get_position'):
                pos_x, pos_y = creature.get_position()
            else:
                pos_x, pos_y = creature.x, creature.y

            if action_type == 'move':
                dx, dy = action.get('direction', (0, 0))
                # Speed affects movement distance (faster creatures can move further)
                # Speed 1-2: normal movement, Speed 3-4: can move 1.5x, Speed 5: can move 2x
                speed_multiplier = 1.0 + (creature.speed - 3) * 0.25
                speed_multiplier = max(0.75, min(2.0, speed_multiplier))  # Clamp between 0.75 and 2.0
                
                # For simplicity, faster creatures just move more efficiently (lower cost)
                # The actual movement distance stays 1 cell, but cost is reduced
                new_x = max(0, min(self.width - 1, pos_x + dx))
                new_y = max(0, min(self.height - 1, pos_y + dy))

                # Check collision with other creatures
                collision = any(
                    c.alive and c.id != creature.id and 
                    (c.x == new_x and c.y == new_y or 
                     (hasattr(c, 'get_position') and c.get_position() == (new_x, new_y)))
                    for c in self.cells
                )

                if not collision:
                    old_x, old_y = creature.x, creature.y
                    creature.x = new_x
                    creature.y = new_y
                    # Movement cost scales with stage and speed
                    # Base cost: 1, reduced by stage and speed
                    base_cost = 1.0
                    stage_reduction = (creature.stage - 1) * 0.1
                    speed_reduction = (creature.speed - 3) * 0.15  # Faster = less cost
                    move_cost = max(0.3, base_cost - stage_reduction - speed_reduction)
                    move_cost = int(move_cost) if move_cost >= 1.0 else (1 if move_cost >= 0.5 else 0)
                    creature.energy -= move_cost
                    # Track energy event: move action, no object, -move_cost energy
                    self.energy_events.add(('move', None, -move_cost))
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} moved to ({new_x}, {new_y})")
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} moved from ({old_x}, {old_y}) to ({new_x}, {new_y})")
                    detailed_events.append({
                        'creature_id': creature.id,
                        'type': 'move',
                        'location': (new_x, new_y)
                    })
                else:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} movement blocked by collision at ({new_x}, {new_y})")

            elif action_type == 'eat':
                target_id = action.get('target_id')
                # Find food item by ID or by position
                if target_id:
                    food_item = next((f for f in self.food if f['id'] == target_id), None)
                else:
                    # If no target_id, try to eat food at current position or adjacent
                    food_item = next(
                        (f for f in self.food if abs(f['x'] - pos_x) <= 1 and abs(f['y'] - pos_y) <= 1),
                        None
                    )
                if food_item:
                    food_type = food_item.get('type', 'apple')
                    energy_value = food_item.get('energy_value', 0)
                    
                    # Get food type properties from config
                    food_config = self.food_type_config.get(food_type, {})
                    is_lethal = food_config.get('is_lethal', False)
                    
                    # Check resource competition - can creature access this resource?
                    if not self.resource_manager.can_access_resource(creature.id, food_item['id']):
                        print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} cannot access resource {food_item['id']} - claimed by another")
                        stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                        events.append(f"{stage_name} {creature.id} tried to eat {food_type} but it's claimed by another creature")
                        continue
                    
                    # Claim resource if not already claimed
                    self.resource_manager.claim_resource(creature.id, food_item['id'])
                    
                    # Remove from spatial index before removing from food list
                    self.spatial_index.remove_object(food_item['id'], food_item['x'], food_item['y'])
                    self.food.remove(food_item)
                    
                    # Mark resource as consumed for regeneration tracking
                    self.resource_manager.mark_resource_consumed(food_item['id'], food_item['x'], food_item['y'])
                    
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    
                    # Check if this food type is lethal
                    if is_lethal:
                        # Lethal food - kill immediately
                        creature.energy = 0
                        creature.alive = False
                        self.energy_events.add(('eat', food_type, energy_value))
                        events.append(f"{stage_name} {creature.id} ate lethal {food_type} at ({food_item['x']}, {food_item['y']}) - DIED!")
                    else:
                        # Regular food - apply energy change
                        # Apply stage 3 bonus if applicable (only for positive energy)
                        if energy_value > 0 and creature.stage == 3 and hasattr(creature, 'parts') and creature.parts.get('mouth') == 'sharp':
                            energy_value = int(energy_value * 1.33)  # 33% bonus
                        
                        if energy_value > 0:
                            creature.energy = min(100, creature.energy + energy_value)
                            self.energy_events.add(('eat', food_type, energy_value))
                            events.append(f"{stage_name} {creature.id} ate {food_type} at ({food_item['x']}, {food_item['y']}) - gained {energy_value} energy")
                        else:
                            creature.energy = max(0, creature.energy + energy_value)
                            self.energy_events.add(('eat', food_type, energy_value))
                            events.append(f"{stage_name} {creature.id} ate {food_type} at ({food_item['x']}, {food_item['y']}) - lost {abs(energy_value)} energy!")
                    
                    detailed_events.append({
                        'creature_id': creature.id,
                        'type': 'eat',
                        'location': (food_item['x'], food_item['y']),
                        'target_id': food_item['id'],
                        'food_type': food_type
                    })

            elif action_type == 'flee':
                dx, dy = action.get('direction', (0, 0))
                new_x = max(0, min(self.width - 1, pos_x + dx))
                new_y = max(0, min(self.height - 1, pos_y + dy))
                creature.x = new_x
                creature.y = new_y
                # Fleeing costs more, but scales with speed (faster creatures flee more efficiently)
                flee_cost = max(1, 3 - creature.speed // 2)
                creature.energy -= flee_cost
                # Track energy event: flee action, no object, -flee_cost energy
                self.energy_events.add(('flee', None, -flee_cost))
                stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                events.append(f"{stage_name} {creature.id} fled to ({new_x}, {new_y})")
                detailed_events.append({
                    'creature_id': creature.id,
                    'type': 'flee',
                    'location': (new_x, new_y)
                })

            elif action_type == 'attack':
                from .combat import Combat
                target_id = action.get('target_id')
                
                # Find target creature
                target_creature = None
                if target_id:
                    target_creature = next((c for c in self.cells if c.id == target_id and c.alive), None)
                else:
                    # If no target_id, find nearest enemy within attack range
                    for other in self.cells:
                        if other.id != creature.id and other.alive and other.player_id != creature.player_id:
                            other_pos_x, other_pos_y = other.x, other.y
                            if hasattr(other, 'get_position'):
                                other_pos_x, other_pos_y = other.get_position()
                            distance = math.sqrt((other_pos_x - pos_x)**2 + (other_pos_y - pos_y)**2)
                            if distance <= 1.5:
                                target_creature = other
                                break
                
                if target_creature and Combat.can_attack(creature, target_creature):
                    # Resolve combat
                    damage, defender_killed, energy_gained = Combat.resolve_combat(creature, target_creature)
                    
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    target_stage_name = "Cell" if target_creature.stage == 1 else ("Multicellular" if target_creature.stage == 2 else "Organism")
                    
                    if defender_killed:
                        events.append(f"{stage_name} {creature.id} attacked and killed {target_stage_name} {target_creature.id} (damage: {damage})")
                        if energy_gained > 0:
                            events.append(f"{stage_name} {creature.id} gained {energy_gained} energy from predation")
                            self.energy_events.add(('attack', f"creature_{target_creature.id}", energy_gained))
                        detailed_events.append({
                            'creature_id': creature.id,
                            'type': 'attack',
                            'target_id': target_creature.id,
                            'damage': damage,
                            'killed': True,
                            'energy_gained': energy_gained
                        })
                    else:
                        events.append(f"{stage_name} {creature.id} attacked {target_stage_name} {target_creature.id} for {damage} damage")
                        detailed_events.append({
                            'creature_id': creature.id,
                            'type': 'attack',
                            'target_id': target_creature.id,
                            'damage': damage,
                            'killed': False
                        })
                    
                    # Track energy event for attack cost
                    self.energy_events.add(('attack', None, -3))
                else:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} attack failed - no valid target")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} tried to attack but no valid target")

            elif action_type == 'reproduce':
                # Check if creature has enough energy
                if creature.energy < 88:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} reproduction failed - insufficient energy ({creature.energy} < 88)")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} tried to reproduce but lacks energy ({creature.energy}/88)")
                    continue
                
                # Check if another creature is at the same position (meeting)
                other_creature = None
                for other in self.cells:
                    if (other.id != creature.id and other.alive and 
                        other.x == pos_x and other.y == pos_y):
                        other_creature = other
                        break
                
                # If no other creature at same position, check adjacent positions
                if other_creature is None:
                    for other in self.cells:
                        if (other.id != creature.id and other.alive):
                            other_pos_x, other_pos_y = other.x, other.y
                            if hasattr(other, 'get_position'):
                                other_pos_x, other_pos_y = other.get_position()
                            # Check if adjacent (within 1 cell)
                            if abs(other_pos_x - pos_x) <= 1 and abs(other_pos_y - pos_y) <= 1:
                                other_creature = other
                                break
                
                # Need another creature to reproduce
                if other_creature is None:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} reproduction failed - no partner nearby")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} tried to reproduce but no partner nearby")
                    continue
                
                # Both creatures must have energy >= 88
                if other_creature.energy < 88:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} reproduction failed - partner {other_creature.id} has insufficient energy ({other_creature.energy} < 88)")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} tried to reproduce but partner {other_creature.id} lacks energy ({other_creature.energy}/88)")
                    continue
                
                # Compatibility check: 70% base chance, modified by traits
                base_compatibility = 0.7
                # Modify compatibility based on color similarity (same color = higher compatibility)
                color_bonus = 0.1 if creature.color == other_creature.color else 0.0
                # Modify compatibility based on diet similarity
                diet_bonus = 0.1 if creature.diet == other_creature.diet else 0.0
                compatibility = min(1.0, base_compatibility + color_bonus + diet_bonus)
                
                # Random check for compatibility
                compatibility_roll = random.random()
                if compatibility_roll > compatibility:
                    # Creatures don't like each other, no reproduction
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} reproduction failed - compatibility check failed ({compatibility_roll:.2f} > {compatibility:.2f})")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} and {other_creature.id} tried to reproduce but were incompatible")
                    continue
                
                # Both creatures meet requirements - one reproduces
                # Create new creature of same type nearby
                directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                random.shuffle(directions)
                reproduction_success = False
                for dx, dy in directions:
                    new_x = max(0, min(self.width - 1, pos_x + dx))
                    new_y = max(0, min(self.height - 1, pos_y + dy))
                    # Check if position is free
                    if not any(c.alive and c.x == new_x and c.y == new_y for c in self.cells):
                        # Create new creature with same traits and stage as parent
                        # Apply genetic variation if specified
                        offspring_traits = creature.traits.copy()
                        genetic_variation = offspring_traits.get('genetic_variation', {})
                        
                        if genetic_variation:
                            # Apply speed variation
                            if 'speed' in genetic_variation:
                                speed_modifier = genetic_variation['speed']
                                base_speed = offspring_traits.get('speed', 3)
                                new_speed = int(base_speed * (1.0 + speed_modifier))
                                new_speed = max(1, min(5, new_speed))  # Clamp to 1-5
                                offspring_traits['speed'] = new_speed
                            
                            # Apply color variation
                            if 'color' in genetic_variation and genetic_variation['color'] == 'varied':
                                import random
                                colors = ['blue', 'red', 'green', 'yellow', 'purple', 'orange', 'pink', 'cyan', 'brown', 'black', 'white']
                                offspring_traits['color'] = random.choice(colors)
                            
                            # Apply strength variation (affects starting energy)
                            strength_modifier = genetic_variation.get('strength', 0.0)
                        
                        if creature.stage == 1:
                            from .cell import Cell
                            new_creature = Cell(
                                creature_id=self._resource_id_counter,
                                traits=offspring_traits,
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        elif creature.stage == 2:
                            from .multicellular import Multicellular
                            new_creature = Multicellular(
                                creature_id=self._resource_id_counter,
                                traits=offspring_traits,
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        else:  # stage 3
                            from .organism import Organism
                            new_creature = Organism(
                                creature_id=self._resource_id_counter,
                                traits=offspring_traits,
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        
                        # Apply starting energy with strength modifier
                        base_energy = 50
                        if genetic_variation and 'strength' in genetic_variation:
                            base_energy = int(base_energy * (1.0 + genetic_variation['strength']))
                        new_creature.energy = base_energy
                        # Reproduction cost scales with stage (higher stage = more efficient)
                        reproduce_cost = max(40, 50 - (creature.stage - 1) * 5)
                        # Both creatures lose energy
                        creature.energy -= reproduce_cost
                        other_creature.energy -= reproduce_cost
                        # Track energy event: reproduce action, no object, -reproduce_cost energy
                        self.energy_events.add(('reproduce', None, -reproduce_cost))
                        self.add_cell(new_creature)
                        self._resource_id_counter += 1
                        stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                        events.append(f"{stage_name} {creature.id} and {other_creature.id} reproduced at ({new_x}, {new_y})")
                        detailed_events.append({
                            'creature_id': creature.id,
                            'type': 'reproduce',
                            'location': (new_x, new_y),
                            'offspring_id': new_creature.id,
                            'partner_id': other_creature.id
                        })
                        reproduction_success = True
                        print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} successfully reproduced with {other_creature.id}, created offspring {new_creature.id}")
                        break
                
                # If no free space found for offspring
                if not reproduction_success:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} reproduction failed - no free space for offspring")
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} and {other_creature.id} tried to reproduce but no space available")

            elif action_type == 'signal':
                # Signal action - communicate with nearby creatures of same player
                nearby_allies = [c for c in self.cells 
                               if c.id != creature.id and c.alive and c.player_id == creature.player_id
                               and abs(c.x - pos_x) <= 3 and abs(c.y - pos_y) <= 3]
                
                if nearby_allies:
                    # Use social system to record communication
                    ally_ids = [c.id for c in nearby_allies]
                    self.social_system.communicate(creature.id, 'signal', ally_ids)
                    
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} signaled {len(nearby_allies)} nearby allies")
                    detailed_events.append({
                        'creature_id': creature.id,
                        'type': 'signal',
                        'allies_count': len(nearby_allies)
                    })
                else:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} signaled but no allies nearby")

            elif action_type == 'claim':
                # Claim territory action - claim current area
                region_x = pos_x // self.region_size
                region_y = pos_y // self.region_size
                region_key = (region_x, region_y)
                
                # Use territory manager
                if self.territory_manager.claim_territory(region_key, creature.id):
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} claimed territory at region ({region_x}, {region_y})")
                    detailed_events.append({
                        'creature_id': creature.id,
                        'type': 'claim',
                        'region': region_key
                    })
                else:
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} tried to claim territory but it's already claimed")

            elif action_type == 'cooperate':
                # Cooperate action - share resources or work together
                target_id = action.get('target_id')
                target_creature = None
                
                if target_id:
                    target_creature = next((c for c in self.cells if c.id == target_id and c.alive), None)
                else:
                    # Find nearest ally
                    for other in self.cells:
                        if other.id != creature.id and other.alive and other.player_id == creature.player_id:
                            other_pos_x, other_pos_y = other.x, other.y
                            if hasattr(other, 'get_position'):
                                other_pos_x, other_pos_y = other.get_position()
                            distance = math.sqrt((other_pos_x - pos_x)**2 + (other_pos_y - pos_y)**2)
                            if distance <= 2:
                                target_creature = other
                                break
                
                if target_creature:
                    # Share energy (creature gives some energy to target)
                    share_amount = min(10, creature.energy // 4)
                    if share_amount > 0:
                        creature.energy -= share_amount
                        target_creature.energy = min(100, target_creature.energy + share_amount)
                        stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                        events.append(f"{stage_name} {creature.id} cooperated with {target_creature.id}, shared {share_amount} energy")
                        detailed_events.append({
                            'creature_id': creature.id,
                            'type': 'cooperate',
                            'target_id': target_creature.id,
                            'energy_shared': share_amount
                        })
                        self.energy_events.add(('cooperate', f"creature_{target_creature.id}", -share_amount))
                else:
                    print(f"[DEBUG] Turn {self.turn}: Creature {creature.id} tried to cooperate but no valid target")

            elif action_type == 'migrate':
                # Migrate action - move toward resource-rich area
                rich_areas = self.resource_manager.get_resource_rich_areas(creature)
                
                if rich_areas:
                    # Move toward richest area
                    target_x, target_y, _ = rich_areas[0]
                    dx = 1 if target_x > pos_x else (-1 if target_x < pos_x else 0)
                    dy = 1 if target_y > pos_y else (-1 if target_y < pos_y else 0)
                    
                    new_x = max(0, min(self.width - 1, pos_x + dx))
                    new_y = max(0, min(self.height - 1, pos_y + dy))
                    
                    # Check collision
                    collision = any(
                        c.alive and c.id != creature.id and 
                        (c.x == new_x and c.y == new_y or 
                         (hasattr(c, 'get_position') and c.get_position() == (new_x, new_y)))
                        for c in self.cells
                    )
                    
                    if not collision:
                        creature.x = new_x
                        creature.y = new_y
                        # Migration cost scales with speed (faster creatures migrate more efficiently)
                        migrate_cost = max(0.5, 1.0 - (creature.speed - 3) * 0.2)
                        migrate_cost = int(migrate_cost) if migrate_cost >= 1.0 else 1
                        creature.energy -= migrate_cost
                        self.energy_events.add(('migrate', None, -migrate_cost))
                        stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                        events.append(f"{stage_name} {creature.id} migrated toward resource-rich area ({new_x}, {new_y})")
                        detailed_events.append({
                            'creature_id': creature.id,
                            'type': 'migrate',
                            'location': (new_x, new_y)
                        })
                else:
                    # No rich areas found, just move randomly
                    import random
                    direction = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
                    new_x = max(0, min(self.width - 1, pos_x + direction[0]))
                    new_y = max(0, min(self.height - 1, pos_y + direction[1]))
                    creature.x = new_x
                    creature.y = new_y
                    creature.energy -= 1

            # Check if creature dies (skip if already dead from lethal food)
            if creature.energy <= 0 and creature.alive:
                creature.alive = False
                stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                events.append(f"{stage_name} {creature.id} died")
                detailed_events.append({
                    'creature_id': creature.id,
                    'type': 'death',
                    'location': (creature.x, creature.y)
                })

            # Age the creature
            creature.age += 1

        # Remove dead cells (optional, or keep for visualization)
        # self.cells = [c for c in self.cells if c.alive]

        # Process resource depletion and regeneration
        self.resource_manager.process_resource_depletion()
        
        # Update environment (weather, hazards, day/night)
        self.environment.update()
        
        # Rebuild spatial index after all position changes
        self.spatial_index.rebuild(self.cells, self.food)
        
        # Respawn resources based on depletion system
        if self.turn % 2 == 0:  # Check every 2 turns
            should_respawn, spawn_amount = self.resource_manager.should_respawn_food(len(self.food))
            if should_respawn and spawn_amount > 0:
                self.spawn_resources(num_food=spawn_amount, num_poison=0)
                # Rebuild spatial index after spawning new food
                self.spatial_index.rebuild(self.cells, self.food)

        self.turn += 1
        return events, detailed_events
    
    def get_energy_events_list(self):
        """
        Get list of unique energy events formatted as strings.
        
        Returns:
            List of strings in format: "action object energy_change"
            Example: ["eat apple +30", "eat banana -20", "move -1"]
        """
        result = []
        # Sort with custom key that handles None values
        # Convert None to empty string for sorting purposes
        sorted_events = sorted(self.energy_events, key=lambda x: (x[0], x[1] or '', x[2]))
        for action, obj, energy_change in sorted_events:
            sign = '+' if energy_change > 0 else ''
            if obj:
                result.append(f"{action} {obj} {sign}{energy_change}")
            else:
                result.append(f"{action} {sign}{energy_change}")
        return result
    
    def reset_energy_events(self):
        """Reset energy events tracker (called when starting new attempt)."""
        self.energy_events = set()

