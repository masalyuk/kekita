"""PromptParser class for parsing natural language into creature traits."""

import re


class PromptParser:
    """Parse player text prompt into structured creature traits."""

    @staticmethod
    def parse(prompt_text: str) -> dict:
        """
        Extract traits from natural language prompt.
        
        Args:
            prompt_text: Player's description of their creature
            
        Returns:
            Dict with color, speed, diet, population, social, etc.
        """
        text_lower = prompt_text.lower()

        # Color extraction
        colors = ['blue', 'red', 'green', 'yellow', 'purple', 'orange', 'pink', 'cyan', 'brown', 'black', 'white']
        color = next((c for c in colors if c in text_lower), 'blue')

        # Speed extraction
        if any(w in text_lower for w in ['fast', 'quick', 'rapid', 'swift', 'speedy']):
            speed = 5
        elif any(w in text_lower for w in ['slow', 'sluggish', 'lazy']):
            speed = 1
        elif any(w in text_lower for w in ['medium', 'moderate', 'average']):
            speed = 3
        else:
            speed = 3  # Default

        # Diet extraction
        if any(w in text_lower for w in ['herbivore', 'herbivorous', 'plant', 'vegetarian', 'vegetation']):
            diet = 'herbivore'
        elif any(w in text_lower for w in ['carnivore', 'carnivorous', 'meat', 'predator', 'hunter']):
            diet = 'carnivore'
        else:
            diet = 'omnivore'

        # Population extraction
        pop_match = re.search(r'(\d+)', prompt_text)
        population = int(pop_match.group(1)) if pop_match else 20

        # Social behavior
        if any(w in text_lower for w in ['group', 'swarm', 'pack', 'herd', 'school', 'flock', 'social']):
            social = 'social'
        elif any(w in text_lower for w in ['solitary', 'alone', 'lone', 'independent']):
            social = 'solitary'
        else:
            social = 'solitary'

        # Aggression (optional)
        if any(w in text_lower for w in ['aggressive', 'hostile', 'violent', 'attack']):
            aggression = 'high'
        elif any(w in text_lower for w in ['peaceful', 'calm', 'gentle', 'docile']):
            aggression = 'low'
        else:
            aggression = 'medium'

        # Size (optional)
        if any(w in text_lower for w in ['large', 'big', 'huge', 'giant']):
            size = 'large'
        elif any(w in text_lower for w in ['small', 'tiny', 'mini']):
            size = 'small'
        else:
            size = 'medium'

        return {
            'color': color,
            'speed': speed,
            'diet': diet,
            'population': population,
            'social': social,
            'aggression': aggression,
            'size': size
        }

