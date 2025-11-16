"""LLMResponseParser class for parsing LLM responses into actions."""

import re


class LLMResponseParser:
    """Parse LLM text response into structured action."""

    @staticmethod
    def parse(response: str) -> dict:
        """
        Convert LLM response to action dict.
        
        Examples:
          "MOVE UP" → {'action': 'move', 'direction': (0, -1)}
          "EAT 1" → {'action': 'eat', 'target_id': 1}
          "FLEE RIGHT" → {'action': 'flee', 'direction': (1, 0)}
          "REPRODUCE" → {'action': 'reproduce'}
        
        Args:
            response: LLM text response
            
        Returns:
            Action dict
        """
        response = response.strip().upper()

        if 'MOVE' in response:
            direction = LLMResponseParser.extract_direction(response)
            return {'action': 'move', 'direction': direction}

        elif 'EAT' in response:
            # Try to extract target ID
            match = re.search(r'\d+', response)
            target_id = int(match.group()) if match else None
            return {'action': 'eat', 'target_id': target_id}

        elif 'FLEE' in response:
            direction = LLMResponseParser.extract_direction(response)
            return {'action': 'flee', 'direction': direction}

        elif 'REPRODUCE' in response or 'REPRODUCTION' in response:
            return {'action': 'reproduce'}
        
        elif 'ATTACK' in response:
            # Try to extract target ID
            match = re.search(r'\d+', response)
            target_id = int(match.group()) if match else None
            return {'action': 'attack', 'target_id': target_id}
        
        elif 'SIGNAL' in response:
            # Signal action - communicate with nearby creatures
            return {'action': 'signal'}
        
        elif 'CLAIM' in response:
            # Claim territory action
            return {'action': 'claim'}
        
        elif 'COOPERATE' in response or 'COOPERATION' in response:
            # Cooperate action - share resources or work together
            match = re.search(r'\d+', response)
            target_id = int(match.group()) if match else None
            return {'action': 'cooperate', 'target_id': target_id}
        
        elif 'MIGRATE' in response:
            # Migrate action - move to resource-rich area
            direction = LLMResponseParser.extract_direction(response)
            return {'action': 'migrate', 'direction': direction}

        else:
            # Fallback: random movement
            import random
            directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
            return {'action': 'move', 'direction': random.choice(directions)}

    @staticmethod
    def extract_direction(response: str) -> tuple:
        """
        Extract (dx, dy) from response containing UP/DOWN/LEFT/RIGHT.
        
        Args:
            response: LLM response text
            
        Returns:
            Tuple (dx, dy) for direction
        """
        response = response.upper()
        if 'UP' in response:
            return (0, -1)
        elif 'DOWN' in response:
            return (0, 1)
        elif 'LEFT' in response:
            return (-1, 0)
        elif 'RIGHT' in response:
            return (1, 0)
        else:
            # Default: random direction if no direction specified
            import random
            directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
            return random.choice(directions)

    @staticmethod
    def parse_batch(response: str, creature_ids: list) -> dict:
        """
        Parse batch LLM response into individual actions.
        
        Args:
            response: LLM batch response (format: "ID:ACTION" lines)
            creature_ids: List of creature IDs in the batch
            
        Returns:
            Dict mapping creature_id to action dict
        """
        actions = {}
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue
            
            # Parse "ID:ACTION" format
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            
            try:
                creature_id = int(parts[0].strip())
                action_str = parts[1].strip()
                
                if creature_id not in creature_ids:
                    continue
                
                # Parse the action string
                action = LLMResponseParser.parse(action_str)
                actions[creature_id] = action
            except (ValueError, IndexError):
                continue
        
        # Fill in missing actions with random moves
        for creature_id in creature_ids:
            if creature_id not in actions:
                import random
                directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                actions[creature_id] = {'action': 'move', 'direction': random.choice(directions)}
        
        return actions

