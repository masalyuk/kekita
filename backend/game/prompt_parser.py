"""PromptParser class for parsing natural language into creature traits."""

import re
import json


class PromptParser:
    """Parse player text prompt into structured creature traits."""

    @staticmethod
    async def parse(prompt_text: str, llm_manager=None, debug_info=None) -> dict:
        """
        Extract traits from natural language prompt using LLM.
        
        Args:
            prompt_text: Player's description of their creature
            llm_manager: LLMManager instance for LLM parsing (optional, falls back to keyword matching)
            
        Returns:
            Dict with color, speed, diet, population, social, etc.
        """
        # Try LLM parsing first if manager is available
        if llm_manager:
            try:
                print(f"[PromptParser] → Calling LLM for prompt: '{prompt_text[:50]}...'")
                json_str = await llm_manager.parse_prompt(prompt_text)
                if debug_info is not None:
                    debug_info['llm_response'] = json_str
                print(f"[PromptParser] → LLM returned JSON string ({len(json_str)} chars): {json_str[:200]}...")
                traits = json.loads(json_str)
                if debug_info is not None:
                    debug_info['raw_traits'] = traits.copy()
                print(f"[PromptParser] → Parsed JSON to traits: {traits}")
                # Validate and normalize traits
                print(f"[PromptParser] → Validating traits...")
                validated = PromptParser._validate_traits(traits, debug_info=debug_info)
                print(f"[PromptParser] ✓ Validation complete: {validated}")
                return validated
            except json.JSONDecodeError as e:
                error_msg = f"JSON decode error: {e}"
                print(f"[PromptParser] ✗ {error_msg}")
                print(f"[PromptParser]   JSON string was: {json_str[:200]}")
                if debug_info is not None:
                    debug_info['errors'].append(error_msg)
                    debug_info['llm_response'] = json_str
                # Fall through to keyword-based parsing
            except Exception as e:
                error_msg = f"LLM parsing failed: {e}"
                print(f"[PromptParser] ✗ {error_msg}")
                import traceback
                traceback.print_exc()
                if debug_info is not None:
                    debug_info['errors'].append(error_msg)
                # Fall through to keyword-based parsing
        
        # Fallback to keyword-based parsing
        print(f"[PromptParser] → Falling back to keyword-based parsing")
        if debug_info is not None:
            debug_info['method'] = 'keyword_fallback'
        return PromptParser._parse_keywords(prompt_text)
    
    @staticmethod
    def _validate_traits(traits: dict, debug_info=None) -> dict:
        """
        Validate and normalize traits from LLM response.
        
        Args:
            traits: Dict with potentially invalid trait values
            debug_info: Optional dict to store debug information
            
        Returns:
            Validated dict with all required traits
        """
        validation_log = []
        original_traits = traits.copy()
        
        # Valid color options
        valid_colors = ['blue', 'red', 'green', 'yellow', 'purple', 'orange', 'pink', 'cyan', 'brown', 'black', 'white']
        color = traits.get('color', 'blue')
        if color not in valid_colors:
            # Try to find a valid color in the string
            original_color = color
            color_lower = str(color).lower()
            color = next((c for c in valid_colors if c in color_lower), 'blue')
            if original_color != color:
                validation_log.append(f"color: '{original_color}' → '{color}'")
        
        # Speed: ensure integer 1-5
        speed = traits.get('speed', 3)
        original_speed = speed
        try:
            speed = int(speed)
            speed = max(1, min(5, speed))
            if original_speed != speed:
                validation_log.append(f"speed: {original_speed} → {speed}")
        except (ValueError, TypeError):
            if speed != 3:
                validation_log.append(f"speed: {speed} → 3 (invalid type)")
            speed = 3
        
        # Diet: ensure valid value
        valid_diets = ['herbivore', 'carnivore', 'omnivore']
        diet = traits.get('diet', 'omnivore')
        if diet not in valid_diets:
            original_diet = diet
            diet_lower = str(diet).lower()
            if 'herb' in diet_lower or 'plant' in diet_lower:
                diet = 'herbivore'
            elif 'carn' in diet_lower or 'meat' in diet_lower or 'pred' in diet_lower:
                diet = 'carnivore'
            else:
                diet = 'omnivore'
            if original_diet != diet:
                validation_log.append(f"diet: '{original_diet}' → '{diet}'")
        
        # Population: ensure positive integer
        population = traits.get('population', 20)
        try:
            population = int(population)
            population = max(1, population)
        except (ValueError, TypeError):
            population = 20
        
        # Social: ensure valid value
        valid_social = ['social', 'solitary']
        social = traits.get('social', 'solitary')
        if social not in valid_social:
            original_social = social
            social_lower = str(social).lower()
            if 'social' in social_lower or 'group' in social_lower or 'pack' in social_lower:
                social = 'social'
            else:
                social = 'solitary'
            if original_social != social:
                validation_log.append(f"social: '{original_social}' → '{social}'")
        
        # Aggression: ensure valid value
        valid_aggression = ['low', 'medium', 'high']
        aggression = traits.get('aggression', 'medium')
        if aggression not in valid_aggression:
            original_aggression = aggression
            aggression_lower = str(aggression).lower()
            if 'high' in aggression_lower or 'aggressive' in aggression_lower:
                aggression = 'high'
            elif 'low' in aggression_lower or 'peaceful' in aggression_lower:
                aggression = 'low'
            else:
                aggression = 'medium'
            if original_aggression != aggression:
                validation_log.append(f"aggression: '{original_aggression}' → '{aggression}'")
        
        # Size: ensure valid value
        valid_sizes = ['small', 'medium', 'large']
        size = traits.get('size', 'medium')
        if size not in valid_sizes:
            original_size = size
            size_lower = str(size).lower()
            if 'large' in size_lower or 'big' in size_lower:
                size = 'large'
            elif 'small' in size_lower or 'tiny' in size_lower:
                size = 'small'
            else:
                size = 'medium'
            if original_size != size:
                validation_log.append(f"size: '{original_size}' → '{size}'")
        
        result = {
            'color': color,
            'speed': speed,
            'diet': diet,
            'population': population,
            'social': social,
            'aggression': aggression,
            'size': size
        }
        
        if validation_log:
            print(f"[PromptParser]   Validation changes: {', '.join(validation_log)}")
            if debug_info is not None:
                debug_info['validation_changes'] = validation_log
        
        return result
    
    @staticmethod
    def _parse_keywords(prompt_text: str) -> dict:
        """
        Fallback keyword-based parsing.
        
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
    
    @staticmethod
    async def merge_traits(current_traits: dict, evolution_description: str, llm_manager=None, debug_info=None) -> dict:
        """
        Intelligently merge current traits with evolution description.
        
        Args:
            current_traits: Dict with existing creature traits
            evolution_description: Player's description of how the creature evolved
            llm_manager: LLMManager instance for LLM merging (optional, falls back to keyword matching)
            debug_info: Optional dict to store debug information
            
        Returns:
            Dict with merged traits (preserves unchanged traits, updates only what's mentioned)
        """
        # Try LLM merging first if manager is available
        if llm_manager:
            try:
                print(f"[PromptParser] → Calling LLM for trait merge: '{evolution_description[:50]}...'")
                json_str = await llm_manager.merge_traits(current_traits, evolution_description)
                if debug_info is not None:
                    debug_info['llm_response'] = json_str
                print(f"[PromptParser] → LLM returned merged JSON string ({len(json_str)} chars): {json_str[:200]}...")
                merged_traits = json.loads(json_str)
                if debug_info is not None:
                    debug_info['raw_traits'] = merged_traits.copy()
                print(f"[PromptParser] → Parsed merged JSON to traits: {merged_traits}")
                # Validate and normalize merged traits
                print(f"[PromptParser] → Validating merged traits...")
                validated = PromptParser._validate_traits(merged_traits, debug_info=debug_info)
                print(f"[PromptParser] ✓ Validation complete: {validated}")
                return validated
            except json.JSONDecodeError as e:
                error_msg = f"JSON decode error: {e}"
                print(f"[PromptParser] ✗ {error_msg}")
                print(f"[PromptParser]   JSON string was: {json_str[:200]}")
                if debug_info is not None:
                    debug_info['errors'].append(error_msg)
                    debug_info['llm_response'] = json_str
                # Fall through to keyword-based merging
            except Exception as e:
                error_msg = f"LLM merging failed: {e}"
                print(f"[PromptParser] ✗ {error_msg}")
                import traceback
                traceback.print_exc()
                if debug_info is not None:
                    debug_info['errors'].append(error_msg)
                # Fall through to keyword-based merging
        
        # Fallback to keyword-based merging (preserves existing traits if not mentioned)
        print(f"[PromptParser] → Falling back to keyword-based trait merging")
        if debug_info is not None:
            debug_info['method'] = 'keyword_fallback'
        return PromptParser._merge_keywords(current_traits, evolution_description)
    
    @staticmethod
    def _merge_keywords(current_traits: dict, evolution_description: str) -> dict:
        """
        Fallback keyword-based trait merging.
        Preserves existing traits if not mentioned in evolution description.
        
        Args:
            current_traits: Dict with existing creature traits
            evolution_description: Player's description of how the creature evolved
            
        Returns:
            Dict with merged traits
        """
        text_lower = evolution_description.lower()
        
        # Check if color is mentioned in evolution description
        colors = ['blue', 'red', 'green', 'yellow', 'purple', 'orange', 'pink', 'cyan', 'brown', 'black', 'white', 'color']
        color_mentioned = any(c in text_lower for c in colors)
        
        # Color: use new if mentioned, otherwise preserve existing
        if color_mentioned:
            color = next((c for c in colors[:-1] if c in text_lower), current_traits.get('color', 'blue'))
        else:
            color = current_traits.get('color', 'blue')
        
        # Speed: check if mentioned
        speed_mentioned = any(w in text_lower for w in ['fast', 'quick', 'rapid', 'swift', 'speedy', 'slow', 'sluggish', 'lazy', 'speed'])
        if speed_mentioned:
            if any(w in text_lower for w in ['fast', 'quick', 'rapid', 'swift', 'speedy']):
                speed = 5
            elif any(w in text_lower for w in ['slow', 'sluggish', 'lazy']):
                speed = 1
            elif any(w in text_lower for w in ['medium', 'moderate', 'average']):
                speed = 3
            else:
                speed = current_traits.get('speed', 3)
        else:
            speed = current_traits.get('speed', 3)
        
        # Diet: check if mentioned
        diet_mentioned = any(w in text_lower for w in ['herbivore', 'carnivore', 'omnivore', 'herbivorous', 'carnivorous', 'plant', 'meat', 'predator', 'hunter', 'diet'])
        if diet_mentioned:
            if any(w in text_lower for w in ['herbivore', 'herbivorous', 'plant', 'vegetarian', 'vegetation']):
                diet = 'herbivore'
            elif any(w in text_lower for w in ['carnivore', 'carnivorous', 'meat', 'predator', 'hunter']):
                diet = 'carnivore'
            else:
                diet = current_traits.get('diet', 'omnivore')
        else:
            diet = current_traits.get('diet', 'omnivore')
        
        # Population: check if mentioned
        pop_match = re.search(r'(\d+)', evolution_description)
        if pop_match:
            population = int(pop_match.group(1))
        else:
            population = current_traits.get('population', 20)
        
        # Social: check if mentioned
        social_mentioned = any(w in text_lower for w in ['group', 'swarm', 'pack', 'herd', 'school', 'flock', 'social', 'solitary', 'alone', 'lone', 'independent'])
        if social_mentioned:
            if any(w in text_lower for w in ['group', 'swarm', 'pack', 'herd', 'school', 'flock', 'social']):
                social = 'social'
            elif any(w in text_lower for w in ['solitary', 'alone', 'lone', 'independent']):
                social = 'solitary'
            else:
                social = current_traits.get('social', 'solitary')
        else:
            social = current_traits.get('social', 'solitary')
        
        # Aggression: check if mentioned
        aggression_mentioned = any(w in text_lower for w in ['aggressive', 'hostile', 'violent', 'attack', 'peaceful', 'calm', 'gentle', 'docile', 'aggression'])
        if aggression_mentioned:
            if any(w in text_lower for w in ['aggressive', 'hostile', 'violent', 'attack']):
                aggression = 'high'
            elif any(w in text_lower for w in ['peaceful', 'calm', 'gentle', 'docile']):
                aggression = 'low'
            else:
                aggression = current_traits.get('aggression', 'medium')
        else:
            aggression = current_traits.get('aggression', 'medium')
        
        # Size: check if mentioned
        size_mentioned = any(w in text_lower for w in ['large', 'big', 'huge', 'giant', 'small', 'tiny', 'mini', 'size'])
        if size_mentioned:
            if any(w in text_lower for w in ['large', 'big', 'huge', 'giant']):
                size = 'large'
            elif any(w in text_lower for w in ['small', 'tiny', 'mini']):
                size = 'small'
            else:
                size = current_traits.get('size', 'medium')
        else:
            size = current_traits.get('size', 'medium')
        
        return {
            'color': color,
            'speed': speed,
            'diet': diet,
            'population': population,
            'social': social,
            'aggression': aggression,
            'size': size
        }

