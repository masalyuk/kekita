"""Simulation class orchestrating game loop and state updates."""

import time
from .stage_manager import StageManager
from .scoring import ScoringSystem


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
        self.scoring = ScoringSystem()  # Scoring system

    def is_population_extinct(self):
        """
        Check if all user creatures (non-predators) in the population are dead.
        Predators are excluded from this check.
        
        Returns:
            True if all user creatures are dead (or only predators remain), False otherwise
        """
        # Get only user creatures (exclude predators which have player_id == None)
        user_creatures = [c for c in self.world.cells if c.player_id is not None]
        
        if not user_creatures:
            return True  # No user creatures means extinct
        
        # Check if all user creatures are dead
        return all(not c.alive for c in user_creatures)

    async def step(self, decision_maker):
        """
        Execute one simulation turn.
        
        Args:
            decision_maker: HybridDecisionMaker instance
            
        Returns:
            Dict with updated world state and events
        """
        turn_start_time = time.perf_counter()
        
        # 1. Get state for each creature and separate into critical vs normal
        actions = {}
        print(f"[DEBUG] ===== Turn {self.world.turn} Starting =====")
        print(f"[DEBUG] Total creatures: {len(self.world.cells)}, Alive: {sum(1 for c in self.world.cells if c.alive)}")
        
        # Separate creatures into critical (rule-based) and normal (can batch LLM)
        critical_creatures = []
        normal_creatures = []
        
        for cell in self.world.cells:
            if not cell.alive:
                print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} is dead, skipping")
                continue

            # Get nearby objects
            nearby = self.world.get_nearby(cell)
            world_state = {'nearby': nearby}
            print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} nearby - food: {len(nearby['food'])}, enemies: {len(nearby['enemy'])}")

            # Check if critical situation
            if decision_maker.is_critical_situation(cell, world_state):
                critical_creatures.append((cell, world_state))
            else:
                normal_creatures.append((cell, world_state))
        
        # 2. Handle critical creatures immediately with rule-based
        for cell, world_state in critical_creatures:
            action = decision_maker.rule_based_decision(cell, world_state)
            actions[cell.id] = action
            print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} (critical) decided: {action}")
        
        # 3. Batch LLM calls for normal creatures (group into batches of 3-5)
        batch_size = 4  # Process 4 creatures per batch
        for i in range(0, len(normal_creatures), batch_size):
            batch = normal_creatures[i:i + batch_size]
            batch_actions = await decision_maker.decide_batch(batch)
            actions.update(batch_actions)
            
            # Debug logging
            for cell, _ in batch:
                print(f"[DEBUG] Turn {self.world.turn}: Cell {cell.id} (Player {cell.player_id}) at ({cell.x}, {cell.y}) decided: {batch_actions.get(cell.id, 'N/A')}")

        # 3. Execute actions and get detailed event info
        print(f"[DEBUG] Turn {self.world.turn}: Executing {len(actions)} actions: {actions}")
        turn_events, detailed_events = self.world.update_cells(actions)
        print(f"[DEBUG] Turn {self.world.turn}: Generated {len(turn_events)} events")
        self.events.extend(turn_events)
        
        # Update scoring based on events
        for event in detailed_events:
            event_type = event.get('type')
            if event_type == 'reproduce':
                self.scoring.record_event('reproduction_count')
            elif event_type == 'attack' and event.get('killed'):
                self.scoring.record_event('combat_kills')
            elif event_type == 'cooperate':
                self.scoring.record_event('cooperation_events')
            elif event_type == 'claim':
                self.scoring.record_event('territories_claimed')
            elif event_type == 'migrate':
                self.scoring.record_event('migration_count')
        
        # Update scoring metrics
        alive_count = sum(1 for c in self.world.cells if c.alive)
        new_achievements = self.scoring.update_turn(self.world.turn, alive_count)
        if new_achievements:
            print(f"[Scoring] New achievements unlocked: {', '.join(new_achievements)}")

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
        
        # Get environment data
        environment_data = {
            'weather': self.world.environment.weather.value if hasattr(self.world.environment.weather, 'value') else str(self.world.environment.weather),
            'is_day': self.world.environment.is_day(),
            'day_night_cycle': self.world.environment.day_night_cycle
        }
        
        # Get territory data
        territories_data = {}
        for region_key, territory in self.world.territory_manager.territories.items():
            territories_data[f"{region_key[0]},{region_key[1]}"] = territory.owner_id
        
        # Get hazards data
        hazards_data = []
        for hazard in self.world.environment.hazards:
            hazards_data.append({
                'x': hazard['x'],
                'y': hazard['y'],
                'radius': hazard['radius'],
                'type': hazard['type'].value if hasattr(hazard['type'], 'value') else str(hazard['type'])
            })
        
        # Get disasters data
        disasters_data = []
        for disaster in self.world.environment.active_disasters:
            disasters_data.append({
                'x': disaster['x'],
                'y': disaster['y'],
                'radius': disaster['radius'],
                'type': disaster['type'].value if hasattr(disaster['type'], 'value') else str(disaster['type']),
                'duration': disaster.get('duration', 0),
                'elapsed': self.world.turn - disaster.get('turn', 0)
            })
        
        # Get regions data (for density visualization)
        regions_data = {}
        for region_key, density in self.world.regions.items():
            regions_data[f"{region_key[0]},{region_key[1]}"] = density
        
        return {
            'creatures': creatures_data,
            'resources': {
                'food': self.world.food,
            },
            'turn': self.world.turn,
            'events': turn_events,
            'evolved_creatures': evolved_creatures,  # Return evolved creatures for sprite regeneration
            'environment': environment_data,
            'territories': territories_data,
            'hazards': hazards_data,
            'disasters': disasters_data,
            'regions': regions_data,
            'scoring': self.scoring.get_score_summary()
        }

