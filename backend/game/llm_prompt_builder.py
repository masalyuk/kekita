"""LLMPromptBuilder class for creating compact LLM prompts."""


class LLMPromptBuilder:
    """Create minimal LLM prompts for creature decision-making."""

    @staticmethod
    def build_prompt(cell, world_state: dict) -> str:
        """
        Create compact LLM prompt (~40-50 tokens).
        
        Args:
            cell: Cell object
            world_state: Dict with 'nearby' containing food, enemy lists
            
        Returns:
            Compact text prompt
        """
        energy = cell.energy
        nearby = world_state['nearby']

        # Compact format with stage info
        stage_info = ""
        if hasattr(cell, 'stage'):
            if cell.stage == 2:
                if hasattr(cell, 'colony') and cell.colony:
                    stage_info = f"Stage2:Colony({len(cell.colony.members)}) "
            elif cell.stage == 3:
                if hasattr(cell, 'parts'):
                    parts_str = f"limbs:{cell.parts.get('limbs',0)} sensors:{cell.parts.get('sensors',0)}"
                    stage_info = f"Stage3:{parts_str} "
        
        prompt = f"E:{energy} @({cell.x},{cell.y}) {stage_info}\n"

        # Add nearest significant objects
        if nearby['food']:
            food = nearby['food'][0]
            direction = LLMPromptBuilder.get_direction_symbol(cell, food)
            prompt += f"FOOD {direction} d{int(food['dist'])} "

        if nearby['enemy']:
            enemy = nearby['enemy'][0]
            direction = LLMPromptBuilder.get_direction_symbol(cell, enemy)
            prompt += f"ENEMY {direction} d{int(enemy['dist'])} "

        # Build available actions based on nearby zone and conditions
        available_actions = ["MOVE"]  # MOVE is always available
        
        # EAT: only if food is nearby (within eating range ~1.5 cells)
        food_nearby = nearby['food'] and nearby['food'][0]['dist'] < 1.5
        if food_nearby:
            available_actions.append("EAT")
        
        # FLEE: always available if there are enemies
        if nearby['enemy']:
            available_actions.append("FLEE")
        
        # REPRODUCE: only if partner nearby (within 1 cell) AND energy >= 88
        can_reproduce = False
        if energy >= 88:
            # Check if there's a partner nearby (same position or adjacent)
            for enemy in nearby['enemy']:
                if enemy['dist'] <= 1:
                    can_reproduce = True
                    break
        
        if can_reproduce:
            available_actions.append("REPRODUCE")
        
        # Build action list string
        actions_str = ", ".join(available_actions)
        prompt += f"\nAction? ({actions_str})"
        
        # Debug logging
        print(f"[DEBUG] LLM Prompt for Creature {cell.id}: Available actions: {actions_str}")
        if not food_nearby and nearby['food']:
            print(f"[DEBUG] Food exists but too far (d={nearby['food'][0]['dist']:.2f} > 1.5), EAT not suggested")
        if energy < 88:
            print(f"[DEBUG] Energy {energy} < 88, REPRODUCE not suggested")
        elif not can_reproduce and nearby['enemy']:
            print(f"[DEBUG] Partner too far (nearest at d={nearby['enemy'][0]['dist']:.2f} > 1), REPRODUCE not suggested")

        return prompt

    @staticmethod
    def get_direction_symbol(cell, target: dict) -> str:
        """
        Return direction symbol based on relative position.
        
        Args:
            cell: Cell object
            target: Dict with 'x' and 'y' keys
            
        Returns:
            Direction emoji or text
        """
        dx = target['x'] - cell.x
        dy = target['y'] - cell.y

        # Use simple text directions for better LLM compatibility
        if abs(dx) > abs(dy):
            return 'RIGHT' if dx > 0 else 'LEFT'
        else:
            return 'DOWN' if dy > 0 else 'UP'

