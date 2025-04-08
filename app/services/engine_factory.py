from typing import Optional, Dict, Any, List, Callable
import logging
from search_engines import Google, Bing, Yahoo, Duckduckgo
from search_engines.multiple_search_engines import MultipleSearchEngines

from app.core.config import settings
from app.utils.user_agent_manager import UserAgentManager
from app.schemas.search import SearchResult
from app.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

# Try to import custom engines, but gracefully handle import errors
try:
    from app.services.custom_engines import CUSTOM_ENGINE_MAPPING
    CUSTOM_ENGINES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import custom engines: {str(e)}")
    logger.warning("Falling back to standard search engine implementations")
    CUSTOM_ENGINES_AVAILABLE = False
    CUSTOM_ENGINE_MAPPING = {}

# Engine mapping for easier instantiation - use custom engines if available and enabled
if CUSTOM_ENGINES_AVAILABLE and settings.USE_USER_AGENT_ROTATION:
    ENGINE_MAPPING = CUSTOM_ENGINE_MAPPING
    logger.info("Using custom search engine implementations with user agent rotation")
else:
    ENGINE_MAPPING = {
        "google": Google,
        "bing": Bing,
        "yahoo": Yahoo,
        "duckduckgo": Duckduckgo
    }
    logger.info("Using standard search engine implementations")

class SearchEngineFactory:
    """Factory class for creating search engine instances."""
    
    def __init__(
        self, 
        proxy: Optional[str] = None,
        proxy_manager: Optional[ProxyManager] = None, 
        timeout: int = settings.SEARCH_TIMEOUT,
        get_proxy_callback: Optional[Callable[[str], Optional[str]]] = None
    ):
        """
        Initialize the engine factory.
        
        Args:
            proxy: Fixed proxy URL to use (if any)
            proxy_manager: ProxyManager for proxy rotation
            timeout: Request timeout in seconds
            get_proxy_callback: Optional callback to get a proxy for a specific engine
        """
        self.fixed_proxy = proxy
        self.proxy_manager = proxy_manager
        self.timeout = timeout
        self.get_proxy_callback = get_proxy_callback
        
        # Initialize user agent manager if rotation is enabled
        self.user_agent_manager = UserAgentManager() if settings.USE_USER_AGENT_ROTATION else None
        
        logger.debug(f"SearchEngineFactory initialized with proxy: {proxy or 'proxy manager' if proxy_manager else 'None'}, timeout: {timeout}s")
        if self.user_agent_manager:
            logger.debug("User agent rotation is enabled")
    
    def get_engine(self, engine_name: str):
        """
        Get a search engine instance by name.
        
        Args:
            engine_name: Name of the search engine to create
            
        Returns:
            Instance of the specified search engine
            
        Raises:
            ValueError: If the engine name is not supported
        """
        logger.debug(f"Creating {engine_name} search engine instance")
        
        if engine_name not in ENGINE_MAPPING:
            logger.error(f"Unsupported search engine: {engine_name}")
            raise ValueError(f"Unsupported search engine: {engine_name}")
        
        engine_class = ENGINE_MAPPING[engine_name]
        
        # Determine which proxy to use for this engine
        proxy = self._get_proxy_for_engine(engine_name)
        
        # Create engine with proxy and timeout
        engine = engine_class(proxy=proxy, timeout=self.timeout)
        
        # Set user agent if rotation is enabled
        if self.user_agent_manager:
            user_agent = self.user_agent_manager.get_random_user_agent()
            engine = self._set_user_agent(engine, user_agent, engine_name)
        
        return engine
    
    def get_multi_engine(self, engines, ignore_duplicates: bool = True):
        """
        Create a MultipleSearchEngines instance.
        
        Args:
            engines: List of engine names to include
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            MultipleSearchEngines instance
        """
        logger.debug(f"Creating MultipleSearchEngines instance with: {engines}")
        
        # For multi-engine, we use the fixed proxy if available
        # or the first proxy from the manager
        proxy = self.fixed_proxy
        if not proxy and self.proxy_manager and self.proxy_manager.proxies:
            proxy = self.proxy_manager.proxies[0]
        
        multi_engine = MultipleSearchEngines(
            engines, 
            proxy=proxy,
            timeout=self.timeout,
            ignore_duplicate_urls=ignore_duplicates
        )
        
        # Set user agent for multi-engine if rotation is enabled
        if self.user_agent_manager:
            user_agent = self.user_agent_manager.get_random_user_agent()
            multi_engine = self._set_user_agent(multi_engine, user_agent, "multi_engine")
        
        return multi_engine
    
    def get_supported_engines(self) -> List[str]:
        """
        Get a list of all supported search engine names.
        
        Returns:
            List of engine names
        """
        return list(ENGINE_MAPPING.keys())
    
    def _get_proxy_for_engine(self, engine_name: str) -> Optional[str]:
        """
        Get the appropriate proxy for a specific search engine.
        
        Args:
            engine_name: Name of the search engine
            
        Returns:
            Proxy URL or None
        """
        # If we have a fixed proxy, always use that
        if self.fixed_proxy:
            return self.fixed_proxy
            
        # If we have a callback, use that to get a proxy
        if self.get_proxy_callback:
            proxy = self.get_proxy_callback(engine_name)
            if proxy:
                return proxy
                
        # If we have a proxy manager, get a proxy from it
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy(preferred_engine=engine_name)
            if proxy:
                return proxy
                
        # Fall back to the proxy from settings if enabled
        if settings.USE_PROXY and settings.PROXY_URL:
            return settings.PROXY_URL
            
        return None
    
    def _set_user_agent(self, engine, user_agent: str, engine_name: str):
        """
        Set the user agent on an engine instance.
        
        Args:
            engine: Search engine instance
            user_agent: User agent string to set
            engine_name: Name of the engine (for logging)
            
        Returns:
            Updated engine instance
        """
        logger.debug(f"Setting user agent on {engine_name}: {user_agent}")
        
        # Try different approaches to set the user agent
        
        # Approach 1: If engine has headers attribute, set it there
        if hasattr(engine, 'headers'):
            engine.headers['User-Agent'] = user_agent
            logger.debug(f"Set User-Agent via 'headers' attribute for {engine_name}")
        
        # Approach 2: If engine has USER_AGENT attribute, set it there
        if hasattr(engine, 'USER_AGENT'):
            engine.USER_AGENT = user_agent
            logger.debug(f"Set User-Agent via 'USER_AGENT' attribute for {engine_name}")
        
        # Approach 3: If engine has set_user_agent method, call it
        if hasattr(engine, 'set_user_agent'):
            engine.set_user_agent(user_agent)
            logger.debug(f"Set User-Agent via 'set_user_agent' method for {engine_name}")
        
        # If engine has _request method, monkey patch it to ensure user agent is set
        if hasattr(engine, '_request'):
            original_request = engine._request
            
            def modified_request(*args, **kwargs):
                # Add or update headers with our user agent
                if 'headers' not in kwargs:
                    kwargs['headers'] = {}
                kwargs['headers']['User-Agent'] = user_agent
                
                return original_request(*args, **kwargs)
            
            engine._request = modified_request
            logger.debug(f"Monkey patched '_request' method for {engine_name}")
        
        return engine 