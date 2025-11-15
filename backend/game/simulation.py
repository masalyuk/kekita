"""Simulation class orchestrating game loop and state updates."""

import time
from .stage_manager import StageManager


class Simulation:
    """Main simulation engine for cellular stage."""

    def __init__(self, world, llm_manager):
        """
        Initialize simulation.
        
        Args:
            world: World instance
            llm_manager: LLMManager instance
        """
        self.world = world
        self.llm_manager = llm_manager
        self.events = []  # Log of game events

    def is_population_extinct(self):
        """
        Check if all creatures in the population are dead.
        
        Returns:
            True if all creatures are dead, False otherwise
        """
        if not self.world.cells:
            return True  # No creatures means extinct
        return all(not c.alive for c in self.world.cells)

    async def step(self, decision_maker):
        """
        Execute one simulation turn.
        
        Args:
            decision_maker: HybridDecisionMaker instance
            
        Returns:
            Dict with updated world state and events
        """
        turn_start_time = time.perf_counter()
        
        # 1. Get state for each creature
        actions = {}
        print(f"[DEBUG] ===== Turn {self.world.turn} Starting =====")
        print(f"[DEBUG] Total creatures: {len(self.world.cells)}, Alive: {sum(1 for c in self.world.cells if c.alive)}")
        
        for cell in self.world.cells:
            if not cell.alive:
                print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} is dead, skipping")
                continue

            # Get nearby objects
            nearby = self.world.get_nearby(cell)
            world_state = {'nearby': nearby}
            print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} nearby - food: {len(nearby['food'])}, enemies: {len(nearby['enemy'])}")

            # 2. Call hybrid decision maker (LLM or rule-based)
            action = await decision_maker.decide(cell, world_state)
            actions[cell.id] = action
            
            # Debug logging
            print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} (Player {cell.player_id}) at ({cell.x}, {cell.y}) decided: {action}")

        # 3. Execute actions and get detailed event info
        print(f"[DEBUG] Turn {self.world.turn}: Executing {len(actions)} actions: {actions}")
        turn_events, detailed_events = self.world.update_cells(actions)
        print(f"[DEBUG] Turn {self.world.turn}: Generated {len(turn_events)} events")
        self.events.extend(turn_events)

        # 4. Check for evolution opportunities (every 5 turns)
        evolution_events = []
        evolved_creatures = []
        if self.world.turn % 5 == 0:
            evolved_creatures = StageManager.check_and_evolve_all(self.world)
            for new_creature in evolved_creatures:
                evolution_events.append(f"Creature {new_creature.id} evolved to Stage {new_creature.stage}!")
                turn_events.extend(evolution_events)

        # 5. Calculate turn duration
        turn_elapsed_time = time.perf_counter() - turn_start_time
        print(f"[DEBUG] ===== Turn {self.world.turn} Complete: {turn_elapsed_time*1000:.2f}ms =====")
        
        # 6. Return new state for frontend
        creatures_data = [c.to_dict() for c in self.world.cells if c.alive]
        # Debug: log creature colors and sprite URLs being sent
        if creatures_data:
            colors_info = ', '.join([f"Creature {c['id']}: color={c.get('color', 'MISSING')}, sprite_url={c.get('sprite_url', 'None')}" for c in creatures_data])
            print(f"[simulation.step] Sending creatures: {colors_info}")
        
        return {
            'creatures': creatures_data,
            'resources': {
                'food': self.world.food,
            },
            'turn': self.world.turn,
            'events': turn_events,
            'evolved_creatures': evolved_creatures  # Return evolved creatures for sprite regeneration
        }

