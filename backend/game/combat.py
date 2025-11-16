"""Combat system for creature battles."""

import random
import math


class Combat:
    """Handle combat resolution between creatures."""
    
    @staticmethod
    def calculate_damage(attacker, defender):
        """
        Calculate damage dealt by attacker to defender.
        
        Args:
            attacker: Creature object attacking
            defender: Creature object being attacked
            
        Returns:
            Damage amount (integer)
        """
        # Base damage based on attacker's energy and stage
        base_damage = 10 + (attacker.energy // 10) + (attacker.stage * 5)
        
        # Stage bonus: higher stage = more damage
        stage_multiplier = 1.0 + (attacker.stage - 1) * 0.2
        
        # Trait bonuses
        trait_bonus = 1.0
        
        # Sharp mouth bonus (for carnivores or organisms with sharp mouth)
        if attacker.diet == 'carnivore':
            trait_bonus += 0.3  # 30% bonus for carnivores
        elif attacker.stage == 3 and hasattr(attacker, 'parts') and attacker.parts.get('mouth') == 'sharp':
            trait_bonus += 0.2  # 20% bonus for sharp mouth
        
        # Speed bonus: faster creatures hit harder
        speed_bonus = 1.0 + (attacker.speed - 3) * 0.1
        
        # Calculate total damage
        damage = int(base_damage * stage_multiplier * trait_bonus * speed_bonus)
        
        return max(1, damage)  # Minimum 1 damage
    
    @staticmethod
    def apply_defense(damage, defender):
        """
        Apply defense reduction to damage.
        
        Args:
            damage: Raw damage amount
            defender: Creature object defending
            
        Returns:
            Reduced damage amount
        """
        defense_value = 0.0
        
        # Stage 3 organisms have defense parts
        if defender.stage == 3 and hasattr(defender, 'parts'):
            defense_map = {
                'armor': 0.5,  # 50% damage reduction
                'spikes': 0.3,  # 30% damage reduction
                'camouflage': 0.2,  # 20% damage reduction
                'none': 0.0
            }
            defense_value = defense_map.get(defender.parts.get('defense', 'none'), 0.0)
        
        # Apply defense reduction
        reduced_damage = int(damage * (1.0 - defense_value))
        
        return max(1, reduced_damage)  # Minimum 1 damage
    
    @staticmethod
    def resolve_combat(attacker, defender):
        """
        Resolve a combat between two creatures.
        
        Args:
            attacker: Creature object attacking
            defender: Creature object being attacked
            
        Returns:
            Tuple of (damage_dealt, defender_killed, energy_gained)
            - damage_dealt: Damage dealt to defender
            - defender_killed: True if defender died
            - energy_gained: Energy gained by attacker (if carnivore and killed)
        """
        # Calculate damage
        raw_damage = Combat.calculate_damage(attacker, defender)
        final_damage = Combat.apply_defense(raw_damage, defender)
        
        # Apply damage to defender
        defender.energy -= final_damage
        
        # Check if defender died
        defender_killed = False
        energy_gained = 0
        
        if defender.energy <= 0:
            defender.energy = 0
            defender.alive = False
            defender_killed = True
            
            # Carnivores gain energy from killing
            if attacker.diet == 'carnivore':
                # Gain energy based on defender's stage and energy (before death)
                base_energy = defender.stage * 15 + (defender.energy + final_damage) // 5
                energy_gained = min(50, base_energy)  # Cap at 50 energy
                attacker.energy = min(100, attacker.energy + energy_gained)
        
        # Attacker loses some energy from attacking (combat cost)
        attack_cost = 3
        attacker.energy = max(0, attacker.energy - attack_cost)
        
        return final_damage, defender_killed, energy_gained
    
    @staticmethod
    def can_attack(creature, target):
        """
        Check if creature can attack target.
        
        Args:
            creature: Creature object
            target: Target creature object
            
        Returns:
            True if attack is possible
        """
        # Must be alive
        if not creature.alive or not target.alive:
            return False
        
        # Must have enough energy (minimum 50 for attack)
        if creature.energy < 50:
            return False
        
        # Cannot attack self
        if creature.id == target.id:
            return False
        
        # Cannot attack same player (for now - could change later)
        if creature.player_id == target.player_id:
            return False
        
        # Must be adjacent (within 1 cell)
        if hasattr(creature, 'get_position'):
            pos_x, pos_y = creature.get_position()
        else:
            pos_x, pos_y = creature.x, creature.y
        
        if hasattr(target, 'get_position'):
            target_x, target_y = target.get_position()
        else:
            target_x, target_y = target.x, target.y
        
        distance = math.sqrt((target_x - pos_x)**2 + (target_y - pos_y)**2)
        
        return distance <= 1.5  # Within attack range

