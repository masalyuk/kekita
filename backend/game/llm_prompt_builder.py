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
        
        # ATTACK: only if enemy nearby (within 1.5 cells) AND energy >= 50
        can_attack = False
        if energy >= 50 and nearby['enemy']:
            # Check if enemy is within attack range
            for enemy in nearby['enemy']:
                if enemy['dist'] <= 1.5:
                    can_attack = True
                    break
        
        if can_attack:
            available_actions.append("ATTACK")
        
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
        
        # Add custom actions if creature has them
        custom_actions = cell.traits.get('custom_actions', [])
        if custom_actions:
            for action in custom_actions:
                action_upper = action.upper()
                if action_upper not in available_actions:
                    available_actions.append(action_upper)
        
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
    def build_batch_prompt(creatures_with_states: list) -> str:
        """
        Create a batch prompt for multiple creatures.
        
        Args:
            creatures_with_states: List of tuples (cell, world_state)
            
        Returns:
            Batch prompt string
        """
        batch_prompt = "Decide actions for multiple creatures. Return one action per creature, format: ID:ACTION\n\n"
        
        for cell, world_state in creatures_with_states:
            nearby = world_state['nearby']
            energy = cell.energy
            
            # Compact creature info
            stage_info = ""
            if hasattr(cell, 'stage'):
                if cell.stage == 2:
                    if hasattr(cell, 'colony') and cell.colony:
                        stage_info = f"Stage2:Colony({len(cell.colony.members)}) "
                elif cell.stage == 3:
                    if hasattr(cell, 'parts'):
                        parts_str = f"limbs:{cell.parts.get('limbs',0)} sensors:{cell.parts.get('sensors',0)}"
                        stage_info = f"Stage3:{parts_str} "
            
            creature_prompt = f"Creature {cell.id}: E:{energy} @({cell.x},{cell.y}) {stage_info}"
            
            # Add nearby objects
            if nearby['food']:
                food = nearby['food'][0]
                direction = LLMPromptBuilder.get_direction_symbol(cell, food)
                creature_prompt += f" FOOD {direction} d{int(food['dist'])}"
            
            if nearby['enemy']:
                enemy = nearby['enemy'][0]
                direction = LLMPromptBuilder.get_direction_symbol(cell, enemy)
                creature_prompt += f" ENEMY {direction} d{int(enemy['dist'])}"
            
            # Build available actions
            available_actions = ["MOVE"]
            food_nearby = nearby['food'] and nearby['food'][0]['dist'] < 1.5
            if food_nearby:
                available_actions.append("EAT")
            if nearby['enemy']:
                available_actions.append("FLEE")
            if energy >= 50 and nearby['enemy']:
                for enemy in nearby['enemy']:
                    if enemy['dist'] <= 1.5:
                        available_actions.append("ATTACK")
                        break
            if energy >= 88:
                for enemy in nearby['enemy']:
                    if enemy['dist'] <= 1:
                        available_actions.append("REPRODUCE")
                        break
            
            # Add custom actions
            custom_actions = cell.traits.get('custom_actions', [])
            if custom_actions:
                for action in custom_actions:
                    action_upper = action.upper()
                    if action_upper not in available_actions:
                        available_actions.append(action_upper)
            
            actions_str = ", ".join(available_actions)
            creature_prompt += f" Actions: {actions_str}\n"
            batch_prompt += creature_prompt
        
        batch_prompt += "\nReturn format: ID:ACTION (one per line, e.g., '1:MOVE UP', '2:EAT 1001')"
        return batch_prompt

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

