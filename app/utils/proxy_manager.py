import random
import logging
import time
from typing import List, Optional, Dict, Tuple
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Manages a pool of proxies and provides rotation mechanisms.
    Tracks proxy health and throttling metrics to optimize distribution.
    """
    
    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize the proxy manager with a list of proxies.
        
        Args:
            proxies: List of proxy URLs in format "http://host:port"
        """
        self.proxies = proxies or []
        if settings.PROXY_URLS and isinstance(settings.PROXY_URLS, list):
            # Add proxies from settings if not already in the list
            for proxy in settings.PROXY_URLS:
                if proxy and proxy not in self.proxies:
                    self.proxies.append(proxy)
        
        # Add default proxy if configured and list is empty
        if not self.proxies and settings.PROXY_URL:
            self.proxies.append(settings.PROXY_URL)
            
        # Proxy health and metrics tracking
        self.proxy_stats: Dict[str, Dict] = {}
        self._current_index = 0
        self._lock = threading.Lock()
        
        # Initialize stats for each proxy
        for proxy in self.proxies:
            self.proxy_stats[proxy] = {
                "requests": 0,
                "errors": 0,
                "last_used": 0,
                "cooling_until": 0,  # Timestamp when proxy becomes available again
                "is_healthy": True
            }
        
        logger.info(f"ProxyManager initialized with {len(self.proxies)} proxies")
        
    def get_proxy(self, preferred_engine: Optional[str] = None) -> Optional[str]:
        """
        Get the next available proxy using a round-robin strategy.
        
        Args:
            preferred_engine: Search engine for which the proxy is requested
            
        Returns:
            Proxy URL or None if no proxies are available
        """
        if not self.proxies:
            logger.warning("No proxies available in the pool")
            return None
            
        with self._lock:
            # If only one proxy available, simply return it
            if len(self.proxies) == 1:
                proxy = self.proxies[0]
                self._update_proxy_stats(proxy, increment=True)
                logger.info(f"Using single proxy: {proxy} for engine: {preferred_engine}")
                return proxy
                
            # Find the next available healthy proxy
            attempts = 0
            max_attempts = len(self.proxies)
            
            while attempts < max_attempts:
                # Get proxy and increment index
                proxy = self.proxies[self._current_index]
                self._current_index = (self._current_index + 1) % len(self.proxies)
                attempts += 1
                
                # Check if proxy is available for use
                stats = self.proxy_stats[proxy]
                current_time = time.time()
                
                if (not stats["is_healthy"] or 
                    stats["cooling_until"] > current_time):
                    # Skip this proxy, it's either unhealthy or cooling down
                    logger.debug(f"Skipping proxy {proxy} - unhealthy or cooling down")
                    continue
                    
                # Update stats and return the proxy
                self._update_proxy_stats(proxy, increment=True)
                logger.info(f"Selected proxy {proxy} for engine {preferred_engine} (attempt {attempts}/{max_attempts})")
                return proxy
                
            # If we've tried all proxies and none are available,
            # return the one with the lowest request count
            least_used_proxy = min(
                self.proxies, 
                key=lambda p: self.proxy_stats[p]["requests"]
            )
            self._update_proxy_stats(least_used_proxy, increment=True)
            logger.warning(f"All proxies were unavailable, using least used proxy: {least_used_proxy}")
            return least_used_proxy
    
    def mark_proxy_error(self, proxy: str, engine: Optional[str] = None) -> None:
        """
        Mark a proxy as having an error, which may indicate rate limiting.
        
        Args:
            proxy: The proxy URL that experienced an error
            engine: The search engine that returned the error
        """
        if not proxy or proxy not in self.proxy_stats:
            return
            
        with self._lock:
            stats = self.proxy_stats[proxy]
            stats["errors"] += 1
            
            # Apply cooling period for this proxy based on error count
            consecutive_errors = stats["errors"]
            
            if consecutive_errors == 1:
                # First error, brief cooling
                cooling_time = 5  # 5 seconds
            elif consecutive_errors < 3:
                # A few errors, medium cooling
                cooling_time = 30  # 30 seconds
            else:
                # Multiple consecutive errors, longer cooling
                cooling_time = 120  # 2 minutes
                # Mark as potentially unhealthy if many consecutive errors
                if consecutive_errors > 5:
                    stats["is_healthy"] = False
                    logger.warning(f"Proxy {proxy} marked as unhealthy after {consecutive_errors} consecutive errors")
            
            # Set the cooling period
            stats["cooling_until"] = time.time() + cooling_time
            logger.info(f"Proxy {proxy} cooling for {cooling_time}s after error with {engine or 'unknown'} engine")
    
    def mark_proxy_success(self, proxy: str) -> None:
        """
        Mark a proxy as having a successful request.
        Resets error count and may restore health status.
        
        Args:
            proxy: The proxy URL that had a successful request
        """
        if not proxy or proxy not in self.proxy_stats:
            return
            
        with self._lock:
            stats = self.proxy_stats[proxy]
            # Reset errors on success
            stats["errors"] = 0
            # Restore health if it was marked unhealthy
            if not stats["is_healthy"]:
                stats["is_healthy"] = True
                logger.info(f"Proxy {proxy} restored to healthy status")
    
    def add_proxy(self, proxy: str) -> None:
        """
        Add a new proxy to the rotation.
        
        Args:
            proxy: Proxy URL to add
        """
        if not proxy:
            return
            
        with self._lock:
            if proxy not in self.proxies:
                self.proxies.append(proxy)
                self.proxy_stats[proxy] = {
                    "requests": 0,
                    "errors": 0,
                    "last_used": 0,
                    "cooling_until": 0,
                    "is_healthy": True
                }
                logger.info(f"Added proxy {proxy} to rotation pool")
    
    def remove_proxy(self, proxy: str) -> None:
        """
        Remove a proxy from the rotation.
        
        Args:
            proxy: Proxy URL to remove
        """
        if not proxy:
            return
            
        with self._lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                if proxy in self.proxy_stats:
                    del self.proxy_stats[proxy]
                logger.info(f"Removed proxy {proxy} from rotation pool")
    
    def get_stats(self) -> Dict[str, Dict]:
        """
        Get stats about all proxies.
        
        Returns:
            Dictionary mapping proxy URLs to their stats
        """
        with self._lock:
            return {
                proxy: {**stats} for proxy, stats in self.proxy_stats.items()
            }
    
    def _update_proxy_stats(self, proxy: str, increment: bool = False) -> None:
        """
        Update usage statistics for a proxy.
        
        Args:
            proxy: The proxy URL to update
            increment: Whether to increment the request counter
        """
        if not proxy or proxy not in self.proxy_stats:
            return
            
        stats = self.proxy_stats[proxy]
        stats["last_used"] = time.time()
        
        if increment:
            stats["requests"] += 1 