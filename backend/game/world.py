"""World class managing game state, creatures, and resources."""

import random
import math


class World:
    """2D grid world containing creatures, food, poison, light."""

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
        self.food = []   # [{x, y, id}, ...]
        self.poison = []
        self.light = []
        self.turn = 0
        self._resource_id_counter = 1000  # Start IDs high to avoid conflicts
        self.max_stage = 1  # Track highest stage present

    def add_cell(self, creature):
        """Add creature to world (works for Cell, Multicellular, Organism)."""
        self.cells.append(creature)
        # Update max stage
        if hasattr(creature, 'stage'):
            self.max_stage = max(self.max_stage, creature.stage)

    def spawn_resources(self, num_food=15, num_poison=5):
        """
        Generate food, poison, light at random positions.
        
        Args:
            num_food: Number of food items to spawn
            num_poison: Number of poison items to spawn
        """
        # Spawn food
        for _ in range(num_food):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            # Avoid spawning on existing cells
            while any(c.x == x and c.y == y for c in self.cells):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
            self.food.append({
                'x': x,
                'y': y,
                'id': self._resource_id_counter
            })
            self._resource_id_counter += 1

        # Spawn poison
        for _ in range(num_poison):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            # Avoid spawning on existing cells
            while any(c.x == x and c.y == y for c in self.cells):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
            self.poison.append({
                'x': x,
                'y': y,
                'id': self._resource_id_counter
            })
            self._resource_id_counter += 1

    def get_nearby(self, creature, radius=None):
        """
        Return nearby objects for a creature.
        
        Args:
            creature: Creature object to check around (Cell, Multicellular, or Organism)
            radius: Search radius (default: 3 for Stage 1-2, larger for Stage 3)
            
        Returns:
            Dict with food, poison, enemy lists, each containing dicts with x, y, dist, id
        """
        # Use detection radius for Stage 3 organisms
        if radius is None:
            if hasattr(creature, 'get_detection_radius'):
                radius = creature.get_detection_radius()
            else:
                radius = 3
        nearby = {
            'food': [],
            'poison': [],
            'enemy': []
        }

        # Get creature position (centroid for multicellular)
        if hasattr(creature, 'get_position'):
            pos_x, pos_y = creature.get_position()
        else:
            pos_x, pos_y = creature.x, creature.y

        # Check food
        for food in self.food:
            dist = math.sqrt((food['x'] - pos_x)**2 + (food['y'] - pos_y)**2)
            if dist <= radius:
                nearby['food'].append({
                    'x': food['x'],
                    'y': food['y'],
                    'id': food['id'],
                    'dist': dist
                })
        nearby['food'].sort(key=lambda f: f['dist'])

        # Check poison
        for poison in self.poison:
            dist = math.sqrt((poison['x'] - pos_x)**2 + (poison['y'] - pos_y)**2)
            if dist <= radius:
                nearby['poison'].append({
                    'x': poison['x'],
                    'y': poison['y'],
                    'id': poison['id'],
                    'dist': dist
                })
        nearby['poison'].sort(key=lambda p: p['dist'])

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
                    self.food.remove(food_item)
                    # Stage 3 organisms with sharp mouth get more energy
                    energy_gain = 30
                    if creature.stage == 3 and hasattr(creature, 'parts') and creature.parts.get('mouth') == 'sharp':
                        energy_gain = 40
                    creature.energy = min(100, creature.energy + energy_gain)
                    stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                    events.append(f"{stage_name} {creature.id} ate food at ({food_item['x']}, {food_item['y']})")
                    detailed_events.append({
                        'creature_id': creature.id,
                        'type': 'eat',
                        'location': (food_item['x'], food_item['y']),
                        'target_id': food_item['id']
                    })

            elif action_type == 'flee':
                dx, dy = action.get('direction', (0, 0))
                new_x = max(0, min(self.width - 1, pos_x + dx))
                new_y = max(0, min(self.height - 1, pos_y + dy))
                creature.x = new_x
                creature.y = new_y
                creature.energy -= 2  # Fleeing costs more
                stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                events.append(f"{stage_name} {creature.id} fled to ({new_x}, {new_y})")
                detailed_events.append({
                    'creature_id': creature.id,
                    'type': 'flee',
                    'location': (new_x, new_y)
                })

            elif action_type == 'reproduce':
                # Limit to 1 creature per player (for testing)
                if creature.player_id is not None:
                    player_creature_count = sum(1 for c in self.cells if c.alive and c.player_id == creature.player_id)
                    if player_creature_count >= 1:
                        # Already has 1 creature, prevent reproduction
                        continue
                
                if creature.energy > 50:
                    # Create new creature of same type nearby
                    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                    random.shuffle(directions)
                    for dx, dy in directions:
                        new_x = max(0, min(self.width - 1, pos_x + dx))
                        new_y = max(0, min(self.height - 1, pos_y + dy))
                        # Check if position is free
                        if not any(c.alive and c.x == new_x and c.y == new_y for c in self.cells):
                            # Create new creature with same traits and stage
                            if creature.stage == 1:
                                from .cell import Cell
                                new_creature = Cell(
                                    creature_id=self._resource_id_counter,
                                    traits=creature.traits,
                                    x=new_x,
                                    y=new_y,
                                    player_id=creature.player_id
                                )
                            elif creature.stage == 2:
                                from .multicellular import Multicellular
                                new_creature = Multicellular(
                                    creature_id=self._resource_id_counter,
                                    traits=creature.traits,
                                    x=new_x,
                                    y=new_y,
                                    player_id=creature.player_id
                                )
                            else:  # stage 3
                                from .organism import Organism
                                new_creature = Organism(
                                    creature_id=self._resource_id_counter,
                                    traits=creature.traits,
                                    x=new_x,
                                    y=new_y,
                                    player_id=creature.player_id
                                )
                            
                            new_creature.energy = 50
                            creature.energy -= 50  # Reproduction cost
                            self.add_cell(new_creature)
                            self._resource_id_counter += 1
                            stage_name = "Cell" if creature.stage == 1 else ("Multicellular" if creature.stage == 2 else "Organism")
                            events.append(f"{stage_name} {creature.id} reproduced at ({new_x}, {new_y})")
                            detailed_events.append({
                                'creature_id': creature.id,
                                'type': 'reproduce',
                                'location': (new_x, new_y),
                                'offspring_id': new_creature.id
                            })
                            break

            # Check if creature dies
            if creature.energy <= 0:
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

        # Respawn some resources occasionally
        if self.turn % 5 == 0:
            if len(self.food) < 10:
                self.spawn_resources(num_food=3, num_poison=0)

        self.turn += 1
        return events, detailed_events

