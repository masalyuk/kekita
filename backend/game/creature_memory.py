"""Memory system for creatures to remember past events."""

from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum


class MemoryEventType(Enum):
    """Types of events that can be stored in memory."""
    FOOD_FOUND = "food_found"
    ENEMY_ENCOUNTER = "enemy_encounter"
    ATTACK = "attack"
    REPRODUCTION = "reproduction"
    POISON_AVOIDED = "poison_avoided"
    TERRITORY_CLAIMED = "territory_claimed"


@dataclass
class MemoryEvent:
    """Represents a single memory event."""
    turn: int
    event_type: MemoryEventType
    location: tuple  # (x, y)
    target: Optional[int] = None  # Target creature/resource ID
    outcome: Optional[str] = None  # Success/failure, energy gained, etc.
    
    def to_compact_string(self) -> str:
        """Convert to compact string format for LLM prompts."""
        loc_str = f"@({self.location[0]},{self.location[1]})"
        type_short = {
            MemoryEventType.FOOD_FOUND: "food",
            MemoryEventType.ENEMY_ENCOUNTER: "enemy",
            MemoryEventType.ATTACK: "attack",
            MemoryEventType.REPRODUCTION: "repro",
            MemoryEventType.POISON_AVOIDED: "poison",
            MemoryEventType.TERRITORY_CLAIMED: "territory"
        }
        event_str = type_short.get(self.event_type, "event")
        result = f"T{self.turn} {event_str}{loc_str}"
        if self.outcome:
            result += f" {self.outcome}"
        return result


class CreatureMemory:
    """Manages memory storage and retrieval for a creature."""
    
    def __init__(self, max_events: int = 10):
        """
        Initialize creature memory.
        
        Args:
            max_events: Maximum number of events to store
        """
        self.max_events = max_events
        self.events: List[MemoryEvent] = []
    
    def add_event(self, turn: int, event_type: MemoryEventType, location: tuple,
                  target: Optional[int] = None, outcome: Optional[str] = None):
        """
        Add a new memory event.
        
        Args:
            turn: Turn number when event occurred
            event_type: Type of event
            location: (x, y) location of event
            target: Optional target ID
            outcome: Optional outcome description
        """
        event = MemoryEvent(turn, event_type, location, target, outcome)
        self.events.append(event)
        
        # Prune oldest events if over limit
        if len(self.events) > self.max_events:
            # Keep most important events (recent + significant)
            # For now, just keep the most recent
            self.events = self.events[-self.max_events:]
    
    def get_recent(self, n: int = 5) -> List[MemoryEvent]:
        """
        Get the last N events.
        
        Args:
            n: Number of recent events to return
            
        Returns:
            List of most recent events
        """
        return self.events[-n:] if len(self.events) > n else self.events
    
    def get_relevant(self, context: Dict) -> List[MemoryEvent]:
        """
        Get events relevant to current situation.
        
        Args:
            context: Dict with context info (e.g., {'hungry': True, 'nearby_enemy': True})
            
        Returns:
            List of relevant events
        """
        relevant = []
        
        for event in self.events:
            is_relevant = False
            
            # Food-related if hungry
            if context.get('hungry', False) and event.event_type == MemoryEventType.FOOD_FOUND:
                is_relevant = True
            
            # Enemy-related if enemy nearby
            if context.get('nearby_enemy', False) and event.event_type in [
                MemoryEventType.ENEMY_ENCOUNTER, MemoryEventType.ATTACK
            ]:
                is_relevant = True
            
            # Poison-related if poison nearby
            if context.get('nearby_poison', False) and event.event_type == MemoryEventType.POISON_AVOIDED:
                is_relevant = True
            
            if is_relevant:
                relevant.append(event)
        
        # Return most recent relevant events (up to 5)
        return relevant[-5:] if len(relevant) > 5 else relevant
    
    def get_by_type(self, event_type: MemoryEventType) -> List[MemoryEvent]:
        """
        Get all events of a specific type.
        
        Args:
            event_type: Type of event to filter
            
        Returns:
            List of events of that type
        """
        return [e for e in self.events if e.event_type == event_type]
    
    def to_compact_string(self, n: int = 5) -> str:
        """
        Convert recent memories to compact string for LLM prompts.
        
        Args:
            n: Number of recent events to include
            
        Returns:
            Compact string format: "M: T15 food@(5,7) | T18 poison@(8,3) | T20 repro"
        """
        if not self.events:
            return ""
        
        recent = self.get_recent(n)
        memory_strings = [e.to_compact_string() for e in recent]
        return "M: " + " | ".join(memory_strings)

