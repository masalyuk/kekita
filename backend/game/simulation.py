"""Simulation class orchestrating game loop and state updates."""

from .creature_memory import MemoryEventType
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

    async def step(self, decision_maker):
        """
        Execute one simulation turn.
        
        Args:
            decision_maker: HybridDecisionMaker instance
            
        Returns:
            Dict with updated world state and events
        """
        # 1. Get state for each creature
        actions = {}
        for cell in self.world.cells:
            if not cell.alive:
                continue

            # Get nearby objects
            nearby = self.world.get_nearby(cell)
            world_state = {'nearby': nearby}

            # Record nearby food/enemies/poison to memory
            if hasattr(cell, 'memory'):
                # Record food found
                if nearby['food']:
                    food = nearby['food'][0]
                    cell.memory.add_event(
                        self.world.turn,
                        MemoryEventType.FOOD_FOUND,
                        (food['x'], food['y']),
                        target=food['id']
                    )
                
                # Record enemy encounter
                if nearby['enemy']:
                    enemy = nearby['enemy'][0]
                    cell.memory.add_event(
                        self.world.turn,
                        MemoryEventType.ENEMY_ENCOUNTER,
                        (enemy['x'], enemy['y']),
                        target=enemy['id']
                    )
                
                # Record poison nearby
                if nearby['poison'] and nearby['poison'][0]['dist'] < 2:
                    poison = nearby['poison'][0]
                    cell.memory.add_event(
                        self.world.turn,
                        MemoryEventType.POISON_AVOIDED,
                        (poison['x'], poison['y']),
                        target=poison['id']
                    )

            # 2. Call hybrid decision maker (LLM or rule-based)
            action = await decision_maker.decide(cell, world_state)
            actions[cell.id] = action

        # 3. Execute actions and get detailed event info
        turn_events, detailed_events = self.world.update_cells(actions)
        self.events.extend(turn_events)

        # 4. Record action outcomes to memory
        for cell in self.world.cells:
            if not cell.alive or not hasattr(cell, 'memory'):
                continue
            
            action = actions.get(cell.id)
            if not action:
                continue
            
            action_type = action.get('action')
            
            # Record specific action outcomes
            if action_type == 'eat':
                # Find if food was actually eaten
                for event in detailed_events:
                    if event.get('creature_id') == cell.id and event.get('type') == 'eat':
                        cell.memory.add_event(
                            self.world.turn,
                            MemoryEventType.FOOD_FOUND,
                            (cell.x, cell.y),
                            outcome='eaten'
                        )
            
            elif action_type == 'reproduce':
                # Check if reproduction succeeded
                for event in detailed_events:
                    if event.get('creature_id') == cell.id and event.get('type') == 'reproduce':
                        cell.memory.add_event(
                            self.world.turn,
                            MemoryEventType.REPRODUCTION,
                            (cell.x, cell.y),
                            outcome='success'
                        )

        # 5. Check for evolution opportunities (every 5 turns)
        evolution_events = []
        if self.world.turn % 5 == 0:
            evolved = StageManager.check_and_evolve_all(self.world)
            for new_creature in evolved:
                evolution_events.append(f"Creature {new_creature.id} evolved to Stage {new_creature.stage}!")
                turn_events.extend(evolution_events)

        # 6. Return new state for frontend
        return {
            'creatures': [c.to_dict() for c in self.world.cells if c.alive],
            'resources': {
                'food': self.world.food,
                'poison': self.world.poison,
            },
            'turn': self.world.turn,
            'events': turn_events
        }

