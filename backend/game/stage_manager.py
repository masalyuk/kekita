"""StageManager class for handling evolution stage progression."""

from .cell import Cell
from .multicellular import Multicellular, Colony
from .organism import Organism


class StageManager:
    """Manages evolution stage progression and world scaling."""
    
    @staticmethod
    def evolve_creature(creature, world):
        """
        Evolve a creature to the next stage.
        
        Args:
            creature: Creature to evolve (Cell, Multicellular, or Organism)
            world: World instance
            
        Returns:
            New evolved creature or None if evolution failed
        """
        if not creature.can_evolve():
            return None
        
        # Check if creature has enough energy for evolution cost
        if creature.energy < creature.evolve_cost():
            return None
        
        # Deduct evolution cost
        creature.energy -= creature.evolve_cost()
        
        # Evolve based on current stage
        if creature.stage == 1:
            # Stage 1 -> Stage 2: Create Multicellular
            new_creature = Multicellular(
                creature_id=creature.id,  # Keep same ID
                traits=creature.traits,
                x=creature.x,
                y=creature.y,
                player_id=creature.player_id
            )
            # Transfer memory
            new_creature.memory = creature.memory
            new_creature.energy = creature.energy
            
            # Replace in world
            world.cells = [c if c.id != creature.id else new_creature for c in world.cells]
            return new_creature
        
        elif creature.stage == 2:
            # Stage 2 -> Stage 3: Create Organism
            # Only if part of a colony with >= 3 members
            if hasattr(creature, 'colony') and creature.colony and len(creature.colony.members) >= 3:
                new_creature = Organism(
                    creature_id=creature.id,
                    traits=creature.traits,
                    x=creature.x,
                    y=creature.y,
                    player_id=creature.player_id
                )
                # Transfer memory
                new_creature.memory = creature.memory
                new_creature.energy = creature.energy
                
                # Remove from colony
                if creature.colony:
                    creature.colony.remove_member(creature)
                
                # Replace in world
                world.cells = [c if c.id != creature.id else new_creature for c in world.cells]
                
                # Scale world if needed
                StageManager.scale_world_for_stage(world, stage=3)
                
                return new_creature
        
        return None
    
    @staticmethod
    def scale_world_for_stage(world, stage):
        """
        Scale world size based on highest stage present.
        
        Args:
            world: World instance
            stage: Target stage (3 requires larger world)
        """
        if stage == 3:
            # Stage 3 requires 40x40 world
            if world.width < 40 or world.height < 40:
                # Expand world
                old_width, old_height = world.width, world.height
                world.width = 40
                world.height = 40
                
                # Move existing creatures to center of new world
                offset_x = (40 - old_width) // 2
                offset_y = (40 - old_height) // 2
                
                for cell in world.cells:
                    cell.x += offset_x
                    cell.y += offset_y
                
                # Expand food/poison distribution
                # (World will respawn resources naturally)
    
    @staticmethod
    def check_and_evolve_all(world):
        """
        Check all creatures and evolve those that can.
        
        Args:
            world: World instance
            
        Returns:
            List of evolved creatures
        """
        evolved = []
        creatures_to_check = list(world.cells)  # Copy list to avoid modification during iteration
        
        for creature in creatures_to_check:
            if creature.alive and creature.can_evolve():
                new_creature = StageManager.evolve_creature(creature, world)
                if new_creature:
                    evolved.append(new_creature)
        
        return evolved

