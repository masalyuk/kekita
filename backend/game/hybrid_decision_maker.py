"""HybridDecisionMaker class combining LLM and rule-based AI."""

import asyncio
import random


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
            world_state: Dict with 'nearby' containing food, poison, enemy lists
            
        Returns:
            Action dict {'action': ..., 'direction': ...}
        """
        # LAYER 1: Critical situation → use rule-based immediately
        if self.is_critical_situation(cell, world_state):
            action = self.rule_based_decision(cell, world_state)
            print(f"[DEBUG] Creature {cell.id}: Critical situation detected, using rule-based: {action}")
            return action

        # LAYER 2: Normal situation → try LLM with timeout
        try:
            action = await asyncio.wait_for(
                self._call_llm(cell, world_state),
                timeout=self.timeout
            )
            print(f"[DEBUG] Creature {cell.id}: LLM decision: {action}")
            return action
        except asyncio.TimeoutError:
            # LAYER 3: LLM timeout → fallback to rule-based
            action = self.rule_based_decision(cell, world_state)
            print(f"[DEBUG] Creature {cell.id}: LLM timeout, using rule-based: {action}")
            return action
        except Exception as e:
            # LAYER 3: LLM error → fallback
            print(f"[DEBUG] Creature {cell.id}: LLM error: {e}, using rule-based")
            action = self.rule_based_decision(cell, world_state)
            print(f"[DEBUG] Creature {cell.id}: Rule-based fallback: {action}")
            return action

    async def _call_llm(self, cell, world_state: dict) -> dict:
        """Call LLM for decision."""
        from .llm_prompt_builder import LLMPromptBuilder
        from .llm_response_parser import LLMResponseParser

        prompt = LLMPromptBuilder.build_prompt(cell, world_state)
        response = await self.llm_manager.generate(prompt)
        action = LLMResponseParser.parse(response)
        return action

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

        # Poison very close
        if world_state['nearby']['poison']:
            if world_state['nearby']['poison'][0]['dist'] < 1:
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

        # Rule 1: Food at current position → eat it
        if nearby['food'] and nearby['food'][0]['dist'] < 1.5:
            action = {'action': 'eat', 'target_id': nearby['food'][0]['id']}
            print(f"[DEBUG] Rule 1: Food nearby, eating")
            return action

        # Rule 2: Very low energy → find food ASAP
        if energy < 20 and nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            action = {'action': 'move', 'direction': direction}
            print(f"[DEBUG] Rule 2: Low energy ({energy}), moving toward food: {direction}")
            return action

        # Rule 3: Poison close → flee
        if nearby['poison'] and nearby['poison'][0]['dist'] < 2:
            direction = self._direction_from(cell, nearby['poison'][0])
            action = {'action': 'flee', 'direction': direction}
            print(f"[DEBUG] Rule 3: Poison nearby, fleeing: {direction}")
            return action

        # Rule 4: Enemy close and weak → flee
        if nearby['enemy'] and nearby['enemy'][0]['dist'] < 2 and energy < 50:
            direction = self._direction_from(cell, nearby['enemy'][0])
            action = {'action': 'flee', 'direction': direction}
            print(f"[DEBUG] Rule 4: Enemy nearby and weak, fleeing: {direction}")
            return action

        # Rule 5: High energy → reproduce
        if energy > 80:
            action = {'action': 'reproduce'}
            print(f"[DEBUG] Rule 5: High energy ({energy}), reproducing")
            return action

        # Rule 6: Food available → move toward it
        if nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            action = {'action': 'move', 'direction': direction}
            print(f"[DEBUG] Rule 6: Food available, moving toward it: {direction}")
            return action

        # Rule 7: Nothing special → random move
        direction = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
        action = {'action': 'move', 'direction': direction}
        print(f"[DEBUG] Rule 7: No special situation, random move: {direction}")
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

