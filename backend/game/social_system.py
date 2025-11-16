"""Social system for creature communication, hierarchy, and cooperation."""

from typing import Dict, List, Optional, Set
from collections import defaultdict


class SocialGroup:
    """Represents a social group of creatures."""
    
    def __init__(self, group_id: int):
        """
        Initialize a social group.
        
        Args:
            group_id: Unique identifier for this group
        """
        self.id = group_id
        self.members: Set[int] = set()  # Set of creature IDs
        self.leader_id: Optional[int] = None
        self.hierarchy: Dict[int, int] = {}  # {creature_id: rank} - lower rank = higher status
    
    def add_member(self, creature_id: int, rank: int = 0):
        """
        Add a member to the group.
        
        Args:
            creature_id: ID of creature to add
            rank: Hierarchy rank (lower = higher status)
        """
        self.members.add(creature_id)
        self.hierarchy[creature_id] = rank
        if self.leader_id is None or rank < self.hierarchy.get(self.leader_id, 999):
            self.leader_id = creature_id
    
    def remove_member(self, creature_id: int):
        """
        Remove a member from the group.
        
        Args:
            creature_id: ID of creature to remove
        """
        self.members.discard(creature_id)
        if creature_id in self.hierarchy:
            del self.hierarchy[creature_id]
        if self.leader_id == creature_id:
            # Reassign leader
            if self.members:
                self.leader_id = min(self.members, key=lambda cid: self.hierarchy.get(cid, 999))
            else:
                self.leader_id = None


class SocialSystem:
    """Manages social groups, communication, and hierarchy."""
    
    def __init__(self, world):
        """
        Initialize social system.
        
        Args:
            world: World instance
        """
        self.world = world
        self.groups: Dict[int, SocialGroup] = {}
        self.creature_groups: Dict[int, int] = {}  # {creature_id: group_id}
        self.communication_log: List[Dict] = []  # Log of communication events
        self._next_group_id = 1
    
    def form_group(self, creature_ids: List[int]) -> int:
        """
        Form a new social group.
        
        Args:
            creature_ids: List of creature IDs to form group
            
        Returns:
            Group ID
        """
        group_id = self._next_group_id
        self._next_group_id += 1
        
        group = SocialGroup(group_id)
        for i, creature_id in enumerate(creature_ids):
            group.add_member(creature_id, rank=i)
            self.creature_groups[creature_id] = group_id
        
        self.groups[group_id] = group
        return group_id
    
    def get_group(self, creature_id: int) -> Optional[SocialGroup]:
        """
        Get social group for a creature.
        
        Args:
            creature_id: ID of creature
            
        Returns:
            SocialGroup if in a group, None otherwise
        """
        group_id = self.creature_groups.get(creature_id)
        return self.groups.get(group_id) if group_id else None
    
    def communicate(self, sender_id: int, message_type: str, target_ids: Optional[List[int]] = None):
        """
        Record a communication event.
        
        Args:
            sender_id: ID of creature sending message
            message_type: Type of message ('food_found', 'danger', 'help', etc.)
            target_ids: Optional list of target creature IDs (None = broadcast to group)
        """
        group = self.get_group(sender_id)
        if group:
            if target_ids is None:
                # Broadcast to group
                target_ids = list(group.members - {sender_id})
            
            self.communication_log.append({
                'sender_id': sender_id,
                'message_type': message_type,
                'target_ids': target_ids,
                'turn': self.world.turn
            })
    
    def get_hierarchy_rank(self, creature_id: int) -> int:
        """
        Get hierarchy rank for a creature.
        
        Args:
            creature_id: ID of creature
            
        Returns:
            Rank (lower = higher status), or 999 if not in group
        """
        group = self.get_group(creature_id)
        if group:
            return group.hierarchy.get(creature_id, 999)
        return 999
    
    def is_leader(self, creature_id: int) -> bool:
        """
        Check if creature is leader of its group.
        
        Args:
            creature_id: ID of creature
            
        Returns:
            True if leader
        """
        group = self.get_group(creature_id)
        return group and group.leader_id == creature_id

