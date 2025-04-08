import time
import random
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class RequestThrottler:
    """
    Utility for throttling requests to avoid rate limiting.
    Implements random delays between requests to mimic human behavior.
    """
    
    def __init__(
        self,
        min_delay: float = None,
        max_delay: float = None,
        use_random_delays: bool = None,
        engine_specific_delays: Dict[str, Tuple[float, float]] = None
    ):
        """
        Initialize the throttler.
        
        Args:
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            use_random_delays: Whether to use random delays
            engine_specific_delays: Dictionary mapping engine names to (min_delay, max_delay) tuples
        """
        # Use provided values or fall back to settings
        self.min_delay = min_delay if min_delay is not None else settings.MIN_REQUEST_DELAY
        self.max_delay = max_delay if max_delay is not None else settings.MAX_REQUEST_DELAY
        self.use_random_delays = use_random_delays if use_random_delays is not None else settings.USE_RANDOM_DELAYS
        
        # Track last request time for each engine
        self.last_request_times: Dict[str, float] = {}
        
        # Engine-specific delay settings (overrides global settings for specific engines)
        self.engine_specific_delays = engine_specific_delays or {}
        
        if self.use_random_delays:
            logger.info(f"Request throttling enabled with random delays: {self.min_delay}-{self.max_delay}s")
    
    def throttle(self, engine_name: str) -> None:
        """
        Apply throttling delay based on the last request time for the given engine.
        
        Args:
            engine_name: Name of the engine being throttled
        """
        current_time = time.time()
        last_request_time = self.last_request_times.get(engine_name, 0)
        time_since_last_request = current_time - last_request_time
        
        # Get engine-specific delay values if available
        min_delay, max_delay = self._get_delay_values(engine_name)
        
        # Determine the delay to use
        if self.use_random_delays:
            delay = random.uniform(min_delay, max_delay)
        else:
            delay = min_delay
        
        # Calculate remaining delay time (if any)
        remaining_delay = max(0, delay - time_since_last_request)
        
        if remaining_delay > 0:
            logger.debug(f"Throttling {engine_name} for {remaining_delay:.2f}s")
            time.sleep(remaining_delay)
        
        # Update the last request time
        self.last_request_times[engine_name] = time.time()
    
    def get_delay(self, engine_name: str) -> float:
        """
        Get the delay that would be applied without actually sleeping.
        Useful for predictive throttling calculations.
        
        Args:
            engine_name: Name of the engine
            
        Returns:
            The delay in seconds that would be applied
        """
        # Get engine-specific delay values if available
        min_delay, max_delay = self._get_delay_values(engine_name)
        
        if self.use_random_delays:
            return random.uniform(min_delay, max_delay)
        else:
            return min_delay
    
    def reset_timer(self, engine_name: Optional[str] = None) -> None:
        """
        Reset the timer for a specific engine or all engines.
        
        Args:
            engine_name: Name of the engine to reset, or None to reset all
        """
        current_time = time.time()
        
        if engine_name is None:
            # Reset all engines
            for engine in self.last_request_times:
                self.last_request_times[engine] = current_time
        else:
            # Reset specific engine
            self.last_request_times[engine_name] = current_time
    
    def _get_delay_values(self, engine_name: str) -> Tuple[float, float]:
        """
        Get min and max delay values for a specific engine.
        
        Args:
            engine_name: Name of the engine
            
        Returns:
            Tuple of (min_delay, max_delay) for the engine
        """
        if engine_name in self.engine_specific_delays:
            return self.engine_specific_delays[engine_name]
        
        return self.min_delay, self.max_delay 