"""Spatial indexing for efficient nearby object queries."""

from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class SpatialIndex:
    """Grid-based spatial partitioning for fast nearby object queries."""
    
    def __init__(self, world_width: int, world_height: int, cell_size: int = 5):
        """
        Initialize spatial index.
        
        Args:
            world_width: Width of world
            world_height: Height of world
            cell_size: Size of grid cells (default: 5)
        """
        self.world_width = world_width
        self.world_height = world_height
        self.cell_size = cell_size
        self.grid_width = (world_width + cell_size - 1) // cell_size
        self.grid_height = (world_height + cell_size - 1) // cell_size
        self.grid: Dict[Tuple[int, int], List] = defaultdict(list)
    
    def _get_grid_coords(self, x: int, y: int) -> Tuple[int, int]:
        """
        Get grid coordinates for a world position.
        
        Args:
            x: World X coordinate
            y: World Y coordinate
            
        Returns:
            (grid_x, grid_y) tuple
        """
        grid_x = x // self.cell_size
        grid_y = y // self.cell_size
        return (grid_x, grid_y)
    
    def add_object(self, obj_id: int, x: int, y: int, obj_type: str = 'creature'):
        """
        Add an object to the spatial index.
        
        Args:
            obj_id: Object ID
            x: X coordinate
            y: Y coordinate
            obj_type: Type of object ('creature', 'food', etc.)
        """
        grid_coords = self._get_grid_coords(x, y)
        self.grid[grid_coords].append({
            'id': obj_id,
            'x': x,
            'y': y,
            'type': obj_type
        })
    
    def remove_object(self, obj_id: int, x: int, y: int):
        """
        Remove an object from the spatial index.
        
        Args:
            obj_id: Object ID
            x: X coordinate
            y: Y coordinate
        """
        grid_coords = self._get_grid_coords(x, y)
        if grid_coords in self.grid:
            self.grid[grid_coords] = [
                obj for obj in self.grid[grid_coords] if obj['id'] != obj_id
            ]
    
    def get_nearby(self, x: int, y: int, radius: int, obj_type: Optional[str] = None) -> List[Dict]:
        """
        Get objects within radius of a position.
        
        Args:
            x: Center X coordinate
            y: Center Y coordinate
            radius: Search radius
            obj_type: Optional filter by object type
            
        Returns:
            List of object dicts
        """
        center_grid = self._get_grid_coords(x, y)
        radius_cells = (radius + self.cell_size - 1) // self.cell_size
        
        nearby = []
        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                check_grid = (center_grid[0] + dx, center_grid[1] + dy)
                if check_grid in self.grid:
                    for obj in self.grid[check_grid]:
                        if obj_type is None or obj['type'] == obj_type:
                            # Calculate actual distance
                            dist_sq = (obj['x'] - x)**2 + (obj['y'] - y)**2
                            if dist_sq <= radius * radius:
                                obj_copy = obj.copy()
                                obj_copy['dist'] = dist_sq ** 0.5
                                nearby.append(obj_copy)
        
        return nearby
    
    def clear(self):
        """Clear all objects from the index."""
        self.grid.clear()
    
    def rebuild(self, creatures: List, food: List):
        """
        Rebuild the entire index from creature and food lists.
        
        Args:
            creatures: List of creature objects
            food: List of food dicts
        """
        self.clear()
        
        for creature in creatures:
            if creature.alive:
                self.add_object(creature.id, creature.x, creature.y, 'creature')
        
        for food_item in food:
            self.add_object(food_item['id'], food_item['x'], food_item['y'], 'food')

