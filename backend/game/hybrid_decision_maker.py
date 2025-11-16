"""HybridDecisionMaker class combining LLM and rule-based AI."""

import asyncio
import random
import time


class HybridDecisionMaker:
    """Hybrid AI: LLM + rule-based fallback for creature decisions."""

    def __init__(self, llm_manager, timeout=10.0):
        """
        Initialize hybrid decision maker.
        
        Args:
            llm_manager: LLMManager instance
            timeout: Timeout in seconds for LLM calls (default: 10 seconds)
        """
        self.llm_manager = llm_manager
        self.timeout = timeout  # seconds

    async def decide(self, cell, world_state: dict) -> dict:
        """
        Make creature decision: try LLM first, fallback to rules if timeout.
        
        Args:
            cell: Cell object
            world_state: Dict with 'nearby' containing food, enemy lists
            
        Returns:
            Action dict {'action': ..., 'direction': ...}
        """
        start_time = time.perf_counter()
        decision_type = None
        
        # LAYER 1: Critical situation → use rule-based immediately
        if self.is_critical_situation(cell, world_state):
            action = self.rule_based_decision(cell, world_state)
            decision_type = "rule-based (critical)"
            print(f"[DEBUG] Creature {cell.id}: Critical situation detected, using rule-based: {action}")
        else:
            # LAYER 2: Normal situation → try LLM with timeout
            try:
                action = await asyncio.wait_for(
                    self._call_llm(cell, world_state),
                    timeout=self.timeout
                )
                decision_type = "LLM"
                print(f"[DEBUG] Creature {cell.id}: LLM decision: {action}")
            except asyncio.TimeoutError:
                # LAYER 3: LLM timeout → fallback to rule-based
                action = self.rule_based_decision(cell, world_state)
                decision_type = "rule-based (timeout)"
                print(f"[WARNING] Creature {cell.id}: LLM timeout, using rule-based: {action}")
            except Exception as e:
                # LAYER 3: LLM error → fallback
                action = self.rule_based_decision(cell, world_state)
                decision_type = "rule-based (error)"
                print(f"[DEBUG] Creature {cell.id}: LLM error: {e}, using rule-based")
                print(f"[DEBUG] Creature {cell.id}: Rule-based fallback: {action}")
        
        elapsed_time = time.perf_counter() - start_time
        print(f"[DEBUG] Creature {cell.id}: Decision time: {elapsed_time*1000:.2f}ms ({decision_type})")
        
        return action

    async def _call_llm(self, cell, world_state: dict) -> dict:
        """Call LLM for decision using chat API."""
        from .llm_prompt_builder import LLMPromptBuilder
        from .llm_response_parser import LLMResponseParser

        prompt = LLMPromptBuilder.build_prompt(cell, world_state)
        response = await self.llm_manager.chat(prompt)
        action = LLMResponseParser.parse(response)
        return action

    async def decide_batch(self, creatures_with_states: list) -> dict:
        """
        Make batch decisions for multiple creatures in a single LLM call.
        
        Args:
            creatures_with_states: List of tuples (cell, world_state)
            
        Returns:
            Dict mapping creature_id to action dict
        """
        from .llm_prompt_builder import LLMPromptBuilder
        from .llm_response_parser import LLMResponseParser
        
        if not creatures_with_states:
            return {}
        
        # Build batch prompt
        batch_prompt = LLMPromptBuilder.build_batch_prompt(creatures_with_states)
        creature_ids = [cell.id for cell, _ in creatures_with_states]
        
        try:
            # Call LLM with batch prompt (allow more tokens for batch)
            response = await asyncio.wait_for(
                self.llm_manager.chat(batch_prompt, max_tokens=100),
                timeout=self.timeout
            )
            # Parse batch response
            actions = LLMResponseParser.parse_batch(response, creature_ids)
            print(f"[DEBUG] Batch LLM decision for {len(creatures_with_states)} creatures")
            return actions
        except (asyncio.TimeoutError, Exception) as e:
            print(f"[WARNING] Batch LLM failed, falling back to individual calls: {e}")
            # Fallback to individual calls
            actions = {}
            for cell, world_state in creatures_with_states:
                try:
                    action = await self._call_llm(cell, world_state)
                    actions[cell.id] = action
                except Exception as e2:
                    print(f"[DEBUG] Individual LLM call failed for {cell.id}: {e2}")
                    actions[cell.id] = self.rule_based_decision(cell, world_state)
            return actions

    def is_critical_situation(self, cell, world_state: dict) -> bool:
        """
        Check if immediate action needed (don't wait for LLM).
        
        Args:
            cell: Cell object
            world_state: Dict with 'nearby' information
            
        Returns:
            True if critical situation detected
        """
        # Low energy
        if cell.energy < 20:
            return True

        # Enemy attacking
        if world_state['nearby']['enemy']:
            if world_state['nearby']['enemy'][0]['dist'] < 1:
                return True

        return False

    def rule_based_decision(self, cell, world_state: dict) -> dict:
        """
        Fast rule-based decision logic.
        
        Args:
            cell: Cell object
            world_state: Dict with 'nearby' information
            
        Returns:
            Action dict
        """
        nearby = world_state['nearby']
        energy = cell.energy

        # Rule 1: Check for special resources first
        if nearby['food'] and nearby['food'][0]['dist'] < 1.5:
            food_item = nearby['food'][0]
            food_type = food_item.get('type', 'apple')
            
            # Water nearby → drink it
            if food_type == 'water':
                action = {'action': 'drink', 'target_id': food_item['id']}
                print(f"[DEBUG] Rule 1: Water nearby, drinking")
                return action
            
            # Shelter nearby → hide in it (especially if enemy nearby)
            if food_type == 'shelter':
                if nearby['enemy'] and nearby['enemy'][0]['dist'] < 2:
                    action = {'action': 'hide', 'target_id': food_item['id']}
                    print(f"[DEBUG] Rule 1: Shelter nearby with enemy, hiding")
                    return action
            
            # Regular food → eat it
            if food_type not in ['water', 'shelter']:
                action = {'action': 'eat', 'target_id': food_item['id']}
                print(f"[DEBUG] Rule 1: Food nearby, eating")
                return action

        # Rule 2: Very low energy → find food ASAP
        if energy < 20 and nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            action = {'action': 'move', 'direction': direction}
            print(f"[DEBUG] Rule 2: Low energy ({energy}), moving toward food: {direction}")
            return action

        # Rule 3: Enemy close and weak → flee
        if nearby['enemy'] and nearby['enemy'][0]['dist'] < 2 and energy < 50:
            direction = self._direction_from(cell, nearby['enemy'][0])
            action = {'action': 'flee', 'direction': direction}
            print(f"[DEBUG] Rule 3: Enemy nearby and weak, fleeing: {direction}")
            return action

        # Rule 3.5: Attack enemy if energy >= 50 and enemy nearby
        if energy >= 50 and nearby['enemy']:
            enemy = nearby['enemy'][0]
            if enemy['dist'] <= 1.5:
                # Prefer attack if carnivore or if enemy is weaker
                enemy_energy = enemy.get('energy', 50)
                if cell.diet == 'carnivore' or energy > enemy_energy:
                    action = {'action': 'attack', 'target_id': enemy['id']}
                    print(f"[DEBUG] Rule 3.5: Attacking enemy {enemy['id']} (energy: {energy} vs {enemy_energy})")
                    return action

        # Rule 4: High energy → reproduce (only if partner nearby)
        if energy >= 88:
            # Check if there's a potential partner nearby (within 1 cell)
            potential_partner = None
            for enemy in nearby['enemy']:
                if enemy['dist'] <= 1:
                    potential_partner = enemy
                    break
            
            if potential_partner:
                action = {'action': 'reproduce'}
                print(f"[DEBUG] Rule 4: High energy ({energy}), partner nearby, attempting reproduction")
                return action
            else:
                # No partner nearby, move toward nearest creature to find a mate
                if nearby['enemy']:
                    direction = self._direction_to(cell, nearby['enemy'][0])
                    action = {'action': 'move', 'direction': direction}
                    print(f"[DEBUG] Rule 4: High energy ({energy}), no partner nearby, moving toward nearest creature: {direction}")
                    return action
                else:
                    # No other creatures visible, just try to reproduce anyway (might find one)
                    action = {'action': 'reproduce'}
                    print(f"[DEBUG] Rule 4: High energy ({energy}), no creatures visible, attempting reproduction")
                    return action

        # Rule 5: Food available → move toward it
        if nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            action = {'action': 'move', 'direction': direction}
            print(f"[DEBUG] Rule 5: Food available, moving toward it: {direction}")
            return action

        # Rule 6: Nothing special → random move
        direction = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
        action = {'action': 'move', 'direction': direction}
        print(f"[DEBUG] Rule 6: No special situation, random move: {direction}")
        return action

    def _direction_to(self, cell, target: dict) -> tuple:
        """
        Calculate direction toward target.
        
        Args:
            cell: Cell object
            target: Dict with 'x' and 'y' keys
            
        Returns:
            Tuple (dx, dy)
        """
        dx = 1 if target['x'] > cell.x else (-1 if target['x'] < cell.x else 0)
        dy = 1 if target['y'] > cell.y else (-1 if target['y'] < cell.y else 0)
        
        # If already at target, return random direction
        if dx == 0 and dy == 0:
            return random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
        
        return (dx, dy)

    def _direction_from(self, cell, target: dict) -> tuple:
        """
        Calculate direction away from target.
        
        Args:
            cell: Cell object
            target: Dict with 'x' and 'y' keys
            
        Returns:
            Tuple (dx, dy)
        """
        dx, dy = self._direction_to(cell, target)
        return (-dx, -dy)

