"""Simulation class orchestrating game loop and state updates."""


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

            # 2. Call hybrid decision maker (LLM or rule-based)
            action = await decision_maker.decide(cell, world_state)
            actions[cell.id] = action

        # 3. Execute actions
        turn_events = self.world.update_cells(actions)
        self.events.extend(turn_events)

        # 4. Return new state for frontend
        return {
            'creatures': [c.to_dict() for c in self.world.cells if c.alive],
            'resources': {
                'food': self.world.food,
                'poison': self.world.poison,
            },
            'turn': self.world.turn,
            'events': turn_events
        }

