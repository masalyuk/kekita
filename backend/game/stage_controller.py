"""StageController class for managing stage timing and progression."""

import time


class StageController:
    """Manages stage timing and progression."""
    
    def __init__(self, stage_duration=20):
        """
        Initialize stage controller.
        
        Args:
            stage_duration: Duration of each stage in seconds (default: 60)
        """
        self.stage_duration = stage_duration
        self.current_stage = 1
        self.stage_start_time = None
        self.stage_ended = False
    
    def start_stage(self, stage_number):
        """
        Start a new stage.
        
        Args:
            stage_number: Stage number (1, 2, or 3)
        """
        self.current_stage = stage_number
        self.stage_start_time = time.time()
        self.stage_ended = False
    
    def get_time_remaining(self):
        """
        Get time remaining in current stage.
        
        Returns:
            Time remaining in seconds (0 if stage ended)
        """
        if self.stage_start_time is None:
            return self.stage_duration
        
        elapsed = time.time() - self.stage_start_time
        remaining = max(0, self.stage_duration - elapsed)
        
        if remaining <= 0 and not self.stage_ended:
            self.stage_ended = True
        
        return remaining
    
    def is_stage_ended(self):
        """
        Check if current stage has ended.
        
        Returns:
            False (no time limits - game ends only when population dies)
        """
        return False  # No time limits - game continues until population dies
    
    def get_stage_info(self):
        """
        Get current stage information.
        
        Returns:
            Dict with stage number (no time limits)
        """
        return {
            'stage': self.current_stage,
            'time_remaining': None,  # No time limits
            'stage_ended': False  # Never ends due to time
        }
    
    def can_advance_to_next_stage(self):
        """
        Check if we can advance to next stage.
        
        Returns:
            True if current stage is not 3 (final stage)
        """
        return self.current_stage < 3

