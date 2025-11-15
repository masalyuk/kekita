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

    def __init__(self, width=20, height=20):
        """
        Initialize the world.
        
        Args:
            width: Grid width
            height: Grid height
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

    def add_cell(self, creature):
        """Add creature to world (works for Cell, Multicellular, Organism)."""
        self.cells.append(creature)
        # Update max stage
        if hasattr(creature, 'stage'):
            self.max_stage = max(self.max_stage, creature.stage)

    def spawn_resources(self, num_food=50, num_poison=0):
        """
        Generate food and poison at random positions with 50/50 distribution.
        
        Args:
            num_food: Total number of items to spawn (will be split 50/50 food/poison)
            num_poison: Ignored (kept for compatibility)
        """
        # Calculate 50/50 split
        total_items = num_food
        num_food_items = total_items // 2
        num_poison_items = total_items - num_food_items
        
        # Determine which poison type is lethal (one of the food types)
        lethal_poison_type = random.choice(self.FOOD_TYPES)
        
        # Spawn food items (50%)
        for _ in range(num_food_items):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            # Avoid spawning on existing cells
            while any(c.x == x and c.y == y for c in self.cells):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
            # Randomly assign a food type
            food_type = random.choice(self.FOOD_TYPES)
            # Random energy gain between 10 and 50
            energy_value = random.randint(10, 50)
            self.food.append({
                'x': x,
                'y': y,
                'id': self._resource_id_counter,
                'type': food_type,
                'is_poison': False,
                'energy_value': energy_value,
                'lethal': False
            })
            self._resource_id_counter += 1
        
        # Spawn poison items (50%)
        for _ in range(num_poison_items):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            # Avoid spawning on existing cells
            while any(c.x == x and c.y == y for c in self.cells):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
            # Randomly assign a food type (poison looks like food)
            poison_type = random.choice(self.FOOD_TYPES)
            # Random energy loss between 10 and 50
            energy_value = -random.randint(10, 50)
            # Check if this is the lethal poison type
            is_lethal = (poison_type == lethal_poison_type)
            self.food.append({
                'x': x,
                'y': y,
                'id': self._resource_id_counter,
                'type': poison_type,
                'is_poison': True,
                'energy_value': energy_value,
                'lethal': is_lethal
            })
            self._resource_id_counter += 1
        
        # Debug logging: print lists of food vs poison
        self._debug_log_food_poison()

    def _debug_log_food_poison(self):
        """Print debug logs showing which items are food and which are poison."""
        safe_food = [f for f in self.food if not f.get('is_poison', False)]
        poison_items = [f for f in self.food if f.get('is_poison', False)]
        
        print(f"[DEBUG] Food/Poison Summary (Total items: {len(self.food)})")
        print(f"[DEBUG] Safe Food ({len(safe_food)} items):")
        for food in safe_food:
            food_type = food.get('type', 'unknown')
            energy = food.get('energy_value', 0)
            print(f"[DEBUG]   - {food_type} @ ({food['x']}, {food['y']}) ID:{food['id']} energy:+{energy}")
        
        print(f"[DEBUG] Poison ({len(poison_items)} items):")
        for poison in poison_items:
            poison_type = poison.get('type', 'unknown')
            energy = poison.get('energy_value', 0)
            lethal = "LETHAL" if poison.get('lethal', False) else "regular"
            print(f"[DEBUG]   - {poison_type} @ ({poison['x']}, {poison['y']}) ID:{poison['id']} energy:{energy} ({lethal})")

    def get_nearby(self, creature, radius=None):
        """
        Return nearby objects for a creature.
        
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

        # Check food (creatures see all food normally, no distinction for poison)
        for food in self.food:
            dist = math.sqrt((food['x'] - pos_x)**2 + (food['y'] - pos_y)**2)
            if dist <= radius:
                nearby['food'].append({
                    'x': food['x'],
                    'y': food['y'],
                    'id': food['id'],
                    'type': food.get('type', 'apple'),  # Include type for frontend
                    'dist': dist
                })
        nearby['food'].sort(key=lambda f: f['dist'])

        # Check enemies (other creatures)
        for other_creature in self.cells:
            if other_creature.id != creature.id and other_creature.alive:
                # Skip if same colony (multicellular)
                if hasattr(creature, 'colony') and hasattr(other_creature, 'colony'):
                    if creature.colony and other_creature.colony and creature.colony.id == other_creature.colony.id:
                        continue
                
                other_pos_x = other_creature.x
                other_pos_y = other_creature.y
                if hasattr(other_creature, 'get_position'):
                    other_pos_x, other_pos_y = other_creature.get_position()
                
                dist = math.sqrt((other_pos_x - pos_x)**2 + (other_pos_y - pos_y)**2)
                if dist <= radius:
                    nearby['enemy'].append({
                        'x': other_pos_x,
                        'y': other_pos_y,
                        'id': other_creature.id,
                        'dist': dist,
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
                    creature.energy -= 1  # Movement cost
                    # Track energy event: move action, no object, -1 energy
                    self.energy_events.add(('move', None, -1))
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
                    is_poison = food_item.get('is_poison', False)
                    energy_value = food_item.get('energy_value', 30 if not is_poison else -20)
                    is_lethal = food_item.get('lethal', False)
                    
                    self.food.remove(food_item)
                    
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    
                    if is_poison:
                        # This is poison - check if it's lethal
                        if is_lethal:
                            # Lethal poison - kill immediately
                            creature.energy = 0
                            creature.alive = False
                            self.energy_events.add(('eat', food_type, energy_value))
                            events.append(f"{stage_name} {creature.id} ate lethal poison {food_type} at ({food_item['x']}, {food_item['y']}) - DIED!")
                        else:
                            # Regular poison - reduce energy by random amount
                            creature.energy = max(0, creature.energy + energy_value)
                            self.energy_events.add(('eat', food_type, energy_value))
                            events.append(f"{stage_name} {creature.id} ate poison {food_type} at ({food_item['x']}, {food_item['y']}) - lost {abs(energy_value)} energy!")
                    else:
                        # Normal food - gain random energy
                        # Apply stage 3 bonus if applicable
                        if creature.stage == 3 and hasattr(creature, 'parts') and creature.parts.get('mouth') == 'sharp':
                            energy_value = int(energy_value * 1.33)  # 33% bonus
                        creature.energy = min(100, creature.energy + energy_value)
                        self.energy_events.add(('eat', food_type, energy_value))
                        events.append(f"{stage_name} {creature.id} ate {food_type} at ({food_item['x']}, {food_item['y']}) - gained {energy_value} energy")
                    
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
                creature.energy -= 2  # Fleeing costs more
                # Track energy event: flee action, no object, -2 energy
                self.energy_events.add(('flee', None, -2))
                stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                events.append(f"{stage_name} {creature.id} fled to ({new_x}, {new_y})")
                detailed_events.append({
                    'creature_id': creature.id,
                    'type': 'flee',
                    'location': (new_x, new_y)
                })

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
                        if creature.stage == 1:
                            from .cell import Cell
                            new_creature = Cell(
                                creature_id=self._resource_id_counter,
                                traits=creature.traits.copy(),
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        elif creature.stage == 2:
                            from .multicellular import Multicellular
                            new_creature = Multicellular(
                                creature_id=self._resource_id_counter,
                                traits=creature.traits.copy(),
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        else:  # stage 3
                            from .organism import Organism
                            new_creature = Organism(
                                creature_id=self._resource_id_counter,
                                traits=creature.traits.copy(),
                                x=new_x,
                                y=new_y,
                                player_id=creature.player_id
                            )
                        
                        new_creature.energy = 50
                        # Both creatures lose energy
                        creature.energy -= 50
                        other_creature.energy -= 50
                        # Track energy event: reproduce action, no object, -50 energy
                        self.energy_events.add(('reproduce', None, -50))
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

            # Check if creature dies (skip if already dead from lethal poison)
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

        # Respawn some resources more frequently (maintain 50/50 distribution)
        if self.turn % 2 == 0:  # Every 2 turns instead of 5
            if len(self.food) < 30:  # Lower threshold: spawn when food < 30 instead of < 10
                self.spawn_resources(num_food=10, num_poison=0)  # Spawn 10 items instead of 3

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
        for action, obj, energy_change in sorted(self.energy_events):
            sign = '+' if energy_change > 0 else ''
            if obj:
                result.append(f"{action} {obj} {sign}{energy_change}")
            else:
                result.append(f"{action} {sign}{energy_change}")
        return result
    
    def reset_energy_events(self):
        """Reset energy events tracker (called when starting new attempt)."""
        self.energy_events = set()

