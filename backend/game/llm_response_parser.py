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

        else:
            # Fallback: stay (no movement)
            return {'action': 'move', 'direction': (0, 0)}

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
            # Default: no movement
            return (0, 0)

