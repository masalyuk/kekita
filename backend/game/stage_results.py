"""StageResults class for calculating and formatting stage results."""


class StageResults:
    """Calculate and format stage results."""
    
    @staticmethod
    def calculate(world, player1_id=1, player2_id=2):
        """
        Calculate stage results for both players.
        
        Args:
            world: World instance
            player1_id: Player 1 ID (default: 1)
            player2_id: Player 2 ID (default: 2)
            
        Returns:
            Dict with results for both players
        """
        # Get creatures for each player
        player1_creatures = [c for c in world.cells if c.alive and c.player_id == player1_id]
        player2_creatures = [c for c in world.cells if c.alive and c.player_id == player2_id]
        
        # Get primary creature for each player (should be only 1, but take first if multiple)
        player1_creature = player1_creatures[0] if player1_creatures else None
        player2_creature = player2_creatures[0] if player2_creatures else None
        
        # Calculate stats for each player
        player1_stats = StageResults._calculate_player_stats(player1_creature, player1_id)
        player2_stats = StageResults._calculate_player_stats(player2_creature, player2_id)
        
        # Determine winner (based on energy, then survival)
        winner = None
        if player1_creature and player2_creature:
            if player1_creature.energy > player2_creature.energy:
                winner = player1_id
            elif player2_creature.energy > player1_creature.energy:
                winner = player2_id
        elif player1_creature and not player2_creature:
            winner = player1_id
        elif player2_creature and not player1_creature:
            winner = player2_id
        
        return {
            'player1': player1_stats,
            'player2': player2_stats,
            'winner': winner,
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

