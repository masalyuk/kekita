"""StageResults class for calculating and formatting stage results."""


class StageResults:
    """Calculate and format stage results."""
    
    @staticmethod
    def calculate(world, player_id=1):
        """
        Calculate stage results for single player.
        
        Args:
            world: World instance
            player_id: Player ID (default: 1)
            
        Returns:
            Dict with results for the player
        """
        # Get creatures for the player
        player_creatures = [c for c in world.cells if c.alive and c.player_id == player_id]
        
        # Get primary creature (should be only 1, but take first if multiple)
        player_creature = player_creatures[0] if player_creatures else None
        
        # Calculate stats for the player
        player_stats = StageResults._calculate_player_stats(player_creature, player_id)
        
        return {
            'player': player_stats,
            'survived': player_creature is not None and player_creature.alive,
            'turn': world.turn
        }
    
    @staticmethod
    def _calculate_player_stats(creature, player_id):
        """
        Calculate stats for a single player.
        
        Args:
            creature: Creature object (or None if dead)
            player_id: Player ID
            
        Returns:
            Dict with player stats
        """
        if creature is None:
            return {
                'player_id': player_id,
                'alive': False,
                'energy': 0,
                'age': 0,
                'stage': 0,
                'survival': False
            }
        
        return {
            'player_id': player_id,
            'alive': creature.alive,
            'energy': creature.energy,
            'age': creature.age,
            'stage': creature.stage,
            'survival': creature.alive,
            'color': creature.color,
            'speed': creature.speed,
            'diet': creature.diet,
            'position': (creature.x, creature.y)
        }

