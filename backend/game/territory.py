"""Territory system for creature territory claiming and management."""

from typing import Dict, Tuple, Optional, List


class Territory:
    """Represents a claimed territory region."""
    
    def __init__(self, region_key: Tuple[int, int], owner_id: int):
        """
        Initialize a territory.
        
        Args:
            region_key: (region_x, region_y) tuple
            owner_id: ID of creature that owns this territory
        """
        self.region_key = region_key
        self.owner_id = owner_id
        self.defense_strength = 1.0  # Territory defense modifier
    
    def can_access(self, creature_id: int) -> bool:
        """
        Check if creature can access this territory.
        
        Args:
            creature_id: ID of creature trying to access
            
        Returns:
            True if creature can access (owner or unclaimed)
        """
        return self.owner_id == creature_id or self.owner_id is None


class TerritoryManager:
    """Manages territory claiming and access."""
    
    def __init__(self, world):
        """
        Initialize territory manager.
        
        Args:
            world: World instance
        """
        self.world = world
        self.territories: Dict[Tuple[int, int], Territory] = {}
    
    def claim_territory(self, region_key: Tuple[int, int], creature_id: int) -> bool:
        """
        Claim a territory region.
        
        Args:
            region_key: (region_x, region_y) tuple
            creature_id: ID of creature claiming
            
        Returns:
            True if successfully claimed
        """
        if region_key in self.territories:
            # Territory already claimed - can only be claimed by owner or if owner is dead
            existing = self.territories[region_key]
            if existing.owner_id == creature_id:
                return True  # Already owned by this creature
            # Check if owner is dead
            owner = next((c for c in self.world.cells if c.id == existing.owner_id), None)
            if owner and owner.alive:
                return False  # Territory is defended
        
        # Claim territory
        self.territories[region_key] = Territory(region_key, creature_id)
        return True
    
    def get_territory_owner(self, region_key: Tuple[int, int]) -> Optional[int]:
        """
        Get owner of a territory region.
        
        Args:
            region_key: (region_x, region_y) tuple
            
        Returns:
            Creature ID if claimed, None otherwise
        """
        territory = self.territories.get(region_key)
        return territory.owner_id if territory else None
    
    def can_access_territory(self, region_key: Tuple[int, int], creature_id: int) -> bool:
        """
        Check if creature can access a territory.
        
        Args:
            region_key: (region_x, region_y) tuple
            creature_id: ID of creature
            
        Returns:
            True if can access
        """
        territory = self.territories.get(region_key)
        if not territory:
            return True  # Unclaimed territory is accessible
        return territory.can_access(creature_id)
    
    def release_territory(self, region_key: Tuple[int, int]):
        """
        Release a territory (when owner dies).
        
        Args:
            region_key: (region_x, region_y) tuple
        """
        if region_key in self.territories:
            del self.territories[region_key]
    
    def get_creature_territories(self, creature_id: int) -> List[Tuple[int, int]]:
        """
        Get all territories owned by a creature.
        
        Args:
            creature_id: ID of creature
            
        Returns:
            List of region keys
        """
        return [key for key, territory in self.territories.items() 
                if territory.owner_id == creature_id]

