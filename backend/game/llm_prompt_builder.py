"""LLMPromptBuilder class for creating compact LLM prompts."""


class LLMPromptBuilder:
    """Create minimal LLM prompts for creature decision-making."""

    @staticmethod
    def build_prompt(cell, world_state: dict) -> str:
        """
        Create compact LLM prompt (~40-50 tokens).
        
        Args:
            cell: Cell object
            world_state: Dict with 'nearby' containing food, poison, enemy lists
            
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

        # Add memory if available
        if hasattr(cell, 'memory') and cell.memory.events:
            memory_str = cell.memory.to_compact_string(n=3)  # Last 3 events
            if memory_str:
                prompt += f"{memory_str}\n"

        # Add nearest significant objects
        if nearby['food']:
            food = nearby['food'][0]
            direction = LLMPromptBuilder.get_direction_symbol(cell, food)
            prompt += f"FOOD {direction} d{int(food['dist'])} "

        if nearby['poison']:
            poison = nearby['poison'][0]
            if poison['dist'] < 3:  # Only mention if close
                direction = LLMPromptBuilder.get_direction_symbol(cell, poison)
                prompt += f"POISON {direction} d{int(poison['dist'])} "

        if nearby['enemy']:
            enemy = nearby['enemy'][0]
            direction = LLMPromptBuilder.get_direction_symbol(cell, enemy)
            prompt += f"ENEMY {direction} d{int(enemy['dist'])} "

        prompt += "\nAction? (MOVE, EAT, FLEE, REPRODUCE)"

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

