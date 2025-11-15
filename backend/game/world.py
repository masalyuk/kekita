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
        self.cells = []  # List of Cell objects
        self.food = []   # [{x, y, id}, ...]
        self.poison = []
        self.light = []
        self.turn = 0
        self._resource_id_counter = 1000  # Start IDs high to avoid conflicts

    def add_cell(self, cell):
        """Add creature to world."""
        self.cells.append(cell)

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

    def get_nearby(self, cell, radius=3):
        """
        Return nearby objects for a cell.
        
        Args:
            cell: Cell object to check around
            radius: Search radius
            
        Returns:
            Dict with food, poison, enemy lists, each containing dicts with x, y, dist, id
        """
        nearby = {
            'food': [],
            'poison': [],
            'enemy': []
        }

        # Check food
        for food in self.food:
            dist = math.sqrt((food['x'] - cell.x)**2 + (food['y'] - cell.y)**2)
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
            dist = math.sqrt((poison['x'] - cell.x)**2 + (poison['y'] - cell.y)**2)
            if dist <= radius:
                nearby['poison'].append({
                    'x': poison['x'],
                    'y': poison['y'],
                    'id': poison['id'],
                    'dist': dist
                })
        nearby['poison'].sort(key=lambda p: p['dist'])

        # Check enemies (other cells)
        for other_cell in self.cells:
            if other_cell.id != cell.id and other_cell.alive:
                dist = math.sqrt((other_cell.x - cell.x)**2 + (other_cell.y - cell.y)**2)
                if dist <= radius:
                    nearby['enemy'].append({
                        'x': other_cell.x,
                        'y': other_cell.y,
                        'id': other_cell.id,
                        'dist': dist,
                        'energy': other_cell.energy
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
        """
        events = []

        # Process actions
        for cell in self.cells:
            if not cell.alive:
                continue

            action = actions.get(cell.id)
            if not action:
                continue

            action_type = action.get('action')

            if action_type == 'move':
                dx, dy = action.get('direction', (0, 0))
                new_x = max(0, min(self.width - 1, cell.x + dx))
                new_y = max(0, min(self.height - 1, cell.y + dy))

                # Check collision with other cells
                collision = any(
                    c.alive and c.id != cell.id and c.x == new_x and c.y == new_y
                    for c in self.cells
                )

                if not collision:
                    cell.x = new_x
                    cell.y = new_y
                    cell.energy -= 1  # Movement cost
                    events.append(f"Cell {cell.id} moved to ({new_x}, {new_y})")

            elif action_type == 'eat':
                target_id = action.get('target_id')
                # Find food item by ID or by position
                if target_id:
                    food_item = next((f for f in self.food if f['id'] == target_id), None)
                else:
                    # If no target_id, try to eat food at current position or adjacent
                    food_item = next(
                        (f for f in self.food if abs(f['x'] - cell.x) <= 1 and abs(f['y'] - cell.y) <= 1),
                        None
                    )
                if food_item:
                    self.food.remove(food_item)
                    cell.energy = min(100, cell.energy + 30)
                    events.append(f"Cell {cell.id} ate food at ({food_item['x']}, {food_item['y']})")

            elif action_type == 'flee':
                dx, dy = action.get('direction', (0, 0))
                new_x = max(0, min(self.width - 1, cell.x + dx))
                new_y = max(0, min(self.height - 1, cell.y + dy))
                cell.x = new_x
                cell.y = new_y
                cell.energy -= 2  # Fleeing costs more
                events.append(f"Cell {cell.id} fled to ({new_x}, {new_y})")

            elif action_type == 'reproduce':
                if cell.energy > 50:
                    # Create new cell nearby
                    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                    random.shuffle(directions)
                    for dx, dy in directions:
                        new_x = max(0, min(self.width - 1, cell.x + dx))
                        new_y = max(0, min(self.height - 1, cell.y + dy))
                        # Check if position is free
                        if not any(c.alive and c.x == new_x and c.y == new_y for c in self.cells):
                            # Create new cell with same traits
                            from .cell import Cell
                            new_cell = Cell(
                                creature_id=self._resource_id_counter,
                                traits={'color': cell.color, 'speed': cell.speed, 'diet': cell.diet},
                                x=new_x,
                                y=new_y
                            )
                            new_cell.energy = 50
                            cell.energy -= 50  # Reproduction cost
                            self.add_cell(new_cell)
                            self._resource_id_counter += 1
                            events.append(f"Cell {cell.id} reproduced at ({new_x}, {new_y})")
                            break

            # Check if cell dies
            if cell.energy <= 0:
                cell.alive = False
                events.append(f"Cell {cell.id} died")

            # Age the cell
            cell.age += 1

        # Remove dead cells (optional, or keep for visualization)
        # self.cells = [c for c in self.cells if c.alive]

        # Respawn some resources occasionally
        if self.turn % 5 == 0:
            if len(self.food) < 10:
                self.spawn_resources(num_food=3, num_poison=0)

        self.turn += 1
        return events

