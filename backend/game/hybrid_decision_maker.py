"""HybridDecisionMaker class combining LLM and rule-based AI."""

import asyncio
import random


class HybridDecisionMaker:
    """Hybrid AI: LLM + rule-based fallback for creature decisions."""

    def __init__(self, llm_manager, timeout=0.5):
        """
        Initialize hybrid decision maker.
        
        Args:
            llm_manager: LLMManager instance
            timeout: Timeout in seconds for LLM calls
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
            return self.rule_based_decision(cell, world_state)

        # LAYER 2: Normal situation → try LLM with timeout
        try:
            action = await asyncio.wait_for(
                self._call_llm(cell, world_state),
                timeout=self.timeout
            )
            return action
        except asyncio.TimeoutError:
            # LAYER 3: LLM timeout → fallback to rule-based
            return self.rule_based_decision(cell, world_state)
        except Exception as e:
            # LAYER 3: LLM error → fallback
            print(f"LLM error: {e}, using rule-based")
            return self.rule_based_decision(cell, world_state)

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
            return {'action': 'eat', 'target_id': nearby['food'][0]['id']}

        # Rule 2: Very low energy → find food ASAP
        if energy < 20 and nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            return {'action': 'move', 'direction': direction}

        # Rule 3: Poison close → flee
        if nearby['poison'] and nearby['poison'][0]['dist'] < 2:
            direction = self._direction_from(cell, nearby['poison'][0])
            return {'action': 'flee', 'direction': direction}

        # Rule 4: Enemy close and weak → flee
        if nearby['enemy'] and nearby['enemy'][0]['dist'] < 2 and energy < 50:
            direction = self._direction_from(cell, nearby['enemy'][0])
            return {'action': 'flee', 'direction': direction}

        # Rule 5: High energy → reproduce
        if energy > 80:
            return {'action': 'reproduce'}

        # Rule 6: Food available → move toward it
        if nearby['food']:
            direction = self._direction_to(cell, nearby['food'][0])
            return {'action': 'move', 'direction': direction}

        # Rule 7: Nothing special → random move
        direction = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
        return {'action': 'move', 'direction': direction}

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

