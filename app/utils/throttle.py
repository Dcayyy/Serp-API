import time
import random
import logging
from typing import Dict, Optional, Tuple, Set

from app.core.config import settings

logger = logging.getLogger(__name__)

class RequestThrottler:
    """
    Class for throttling requests to prevent rate limiting by search engines.
    """
    
    def __init__(
        self,
        min_delay: float = settings.MIN_REQUEST_DELAY,
        max_delay: float = settings.MAX_REQUEST_DELAY,
        use_random_delays: bool = settings.USE_RANDOM_DELAYS,
        engine_specific_delays: Optional[Dict[str, Tuple[float, float]]] = None
    ):
        """
        Initialize the request throttler.
        
        Args:
            min_delay: Minimum delay in seconds between requests
            max_delay: Maximum delay in seconds between requests
            use_random_delays: Whether to use random delays between min_delay and max_delay
            engine_specific_delays: Dict mapping engine names to (min_delay, max_delay) tuples
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_random_delays = use_random_delays
        self.engine_specific_delays = engine_specific_delays or settings.ENGINE_SPECIFIC_DELAYS
        
        # Track the last request time for each engine
        self.last_request_times: Dict[str, float] = {}
        
        # Track per-engine success/failure stats to allow adaptive throttling
        self.engine_stats: Dict[str, Dict] = {}
        
        # Recently used engines - for distributed throttling awareness
        self.recent_engines: Set[str] = set()
        
        # Log initialization
        logger.info(f"Request throttling enabled with {'random' if use_random_delays else 'fixed'} delays: {min_delay}-{max_delay}s")
        if self.engine_specific_delays:
            for engine, (min_d, max_d) in self.engine_specific_delays.items():
                logger.debug(f"Engine-specific delay for {engine}: {min_d}-{max_d}s")
    
    def throttle(self, engine_name: str) -> float:
        """
        Apply throttling based on the last request time.
        This method will sleep for the appropriate amount of time.
        
        Args:
            engine_name: Name of the search engine being accessed
            
        Returns:
            The actual delay applied in seconds
        """
        delay = self._calculate_delay(engine_name)
        
        # Apply the delay by sleeping
        if delay > 0:
            logger.debug(f"Throttling {engine_name} request for {delay:.2f}s")
            time.sleep(delay)
        
        # Record this request time
        current_time = time.time()
        self.last_request_times[engine_name] = current_time
        self.recent_engines.add(engine_name)
        
        # Make sure the recent engines set doesn't grow indefinitely
        if len(self.recent_engines) > 10:
            # Remove oldest engines (we don't track ordering, so just reset if too large)
            self.recent_engines = set(self.last_request_times.keys())
        
        return delay
    
    def get_delay(self, engine_name: str) -> float:
        """
        Get the delay that would be applied without actually sleeping.
        Useful for predictive calculations.
        
        Args:
            engine_name: Name of the search engine
            
        Returns:
            Delay in seconds
        """
        return self._calculate_delay(engine_name)
    
    def _calculate_delay(self, engine_name: str) -> float:
        """
        Calculate the appropriate delay based on last request time and engine settings.
        
        Args:
            engine_name: Name of the search engine
            
        Returns:
            Delay in seconds
        """
        current_time = time.time()
        min_delay, max_delay = self._get_delay_values(engine_name)
        
        # Check if there's a previous request time for this engine
        if engine_name in self.last_request_times:
            last_time = self.last_request_times[engine_name]
            elapsed = current_time - last_time
            
            # If other engines have been used recently, reduce the delay
            # as the distributed load is already providing some throttling
            if len(self.recent_engines) > 1 and elapsed > 0:
                if engine_name in self.engine_stats and self.engine_stats[engine_name].get('rate_limit_detected', False):
                    # Don't reduce delay if rate limiting has been detected
                    pass
                else:
                    # Reduce delay based on number of recent engines
                    reduction_factor = min(0.8, 0.3 * len(self.recent_engines))
                    min_delay *= (1 - reduction_factor)
                    max_delay *= (1 - reduction_factor)
            
            # If elapsed time is less than minimum delay, wait the remaining time
            if elapsed < min_delay:
                base_delay = min_delay - elapsed
            else:
                # Already waited long enough
                return 0
        else:
            # First request for this engine, use a small initial delay
            base_delay = min_delay * 0.5
        
        # Add randomness if enabled
        if self.use_random_delays and min_delay < max_delay:
            delay = base_delay + random.uniform(0, max_delay - min_delay)
        else:
            delay = base_delay
        
        return max(0, delay)
    
    def _get_delay_values(self, engine_name: str) -> Tuple[float, float]:
        """
        Get the min and max delay values for a specific engine.
        
        Args:
            engine_name: Name of the search engine
            
        Returns:
            Tuple of (min_delay, max_delay) in seconds
        """
        # Check if we have engine-specific delays
        if self.engine_specific_delays and engine_name in self.engine_specific_delays:
            return self.engine_specific_delays[engine_name]
        
        # Otherwise use the default delays
        return (self.min_delay, self.max_delay)
    
    def reset_timer(self, engine_name: Optional[str] = None) -> None:
        """
        Reset the throttling timer for a specific engine or all engines.
        
        Args:
            engine_name: Name of the search engine to reset, or None for all engines
        """
        if engine_name:
            if engine_name in self.last_request_times:
                del self.last_request_times[engine_name]
                logger.debug(f"Reset throttling timer for {engine_name}")
        else:
            # Reset all engines
            self.last_request_times.clear()
            logger.debug("Reset all throttling timers")
    
    def record_rate_limit_detected(self, engine_name: str) -> None:
        """
        Record that rate limiting was detected for an engine.
        This will increase delays for future requests.
        
        Args:
            engine_name: Name of the search engine
        """
        if engine_name not in self.engine_stats:
            self.engine_stats[engine_name] = {
                'rate_limit_count': 0,
                'rate_limit_detected': False,
                'success_count': 0
            }
        
        stats = self.engine_stats[engine_name]
        stats['rate_limit_count'] = stats.get('rate_limit_count', 0) + 1
        
        # Set rate limit detected flag if we've had multiple incidents
        if stats['rate_limit_count'] >= 2:
            stats['rate_limit_detected'] = True
            
            # Increase delays for this engine by 50%
            if engine_name in self.engine_specific_delays:
                min_delay, max_delay = self.engine_specific_delays[engine_name]
                self.engine_specific_delays[engine_name] = (min_delay * 1.5, max_delay * 1.5)
            
            logger.warning(f"Rate limiting detected for {engine_name}, increased delays by 50%")
    
    def record_success(self, engine_name: str) -> None:
        """
        Record a successful request without rate limiting.
        After multiple successes, delays might be gradually reduced.
        
        Args:
            engine_name: Name of the search engine
        """
        if engine_name not in self.engine_stats:
            self.engine_stats[engine_name] = {
                'rate_limit_count': 0,
                'rate_limit_detected': False,
                'success_count': 0
            }
        
        stats = self.engine_stats[engine_name]
        stats['success_count'] = stats.get('success_count', 0) + 1
        
        # After 10 consecutive successes, gradually reduce delays if they were increased
        if (stats['success_count'] >= 10 and 
            stats['rate_limit_detected'] and 
            engine_name in self.engine_specific_delays):
            
            min_delay, max_delay = self.engine_specific_delays[engine_name]
            
            # Get original delays from settings
            original_min, original_max = settings.ENGINE_SPECIFIC_DELAYS.get(
                engine_name, (settings.MIN_REQUEST_DELAY, settings.MAX_REQUEST_DELAY)
            )
            
            # Reduce by 10% but don't go below original values
            new_min = max(original_min, min_delay * 0.9)
            new_max = max(original_max, max_delay * 0.9)
            
            # Update if they changed
            if new_min < min_delay or new_max < max_delay:
                self.engine_specific_delays[engine_name] = (new_min, new_max)
                stats['success_count'] = 0  # Reset success count
                logger.info(f"Reducing delays for {engine_name} after consistent successes") 