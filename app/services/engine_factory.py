from typing import Optional
import logging
from search_engines import Google, Bing, Yahoo, Duckduckgo
from search_engines.multiple_search_engines import MultipleSearchEngines

from app.core.config import settings
from app.utils.user_agent_manager import UserAgentManager
from app.services.custom_engines import CUSTOM_ENGINE_MAPPING

logger = logging.getLogger(__name__)

# Engine mapping for easier instantiation
ENGINE_MAPPING = CUSTOM_ENGINE_MAPPING if settings.USE_USER_AGENT_ROTATION else {
    "google": Google,
    "bing": Bing,
    "yahoo": Yahoo,
    "duckduckgo": Duckduckgo
}

logger.info(f"Using {'custom' if settings.USE_USER_AGENT_ROTATION else 'standard'} search engine implementations")

class EngineFactory:
    """Factory class for creating search engine instances."""
    
    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        """
        Initialize the engine factory.
        
        Args:
            proxy: Proxy URL to use (if any)
            timeout: Request timeout in seconds
        """
        self.proxy = proxy
        self.timeout = timeout
        
        # Initialize user agent manager if rotation is enabled
        self.user_agent_manager = UserAgentManager() if settings.USE_USER_AGENT_ROTATION else None
        
        logger.debug(f"EngineFactory initialized with proxy: {proxy or 'None'}, timeout: {timeout}s")
        if self.user_agent_manager:
            logger.debug("User agent rotation is enabled")
    
    def create_engine(self, engine_name: str):
        """
        Create a search engine instance by name.
        
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
        
        # Create engine with proxy and timeout
        engine = engine_class(proxy=self.proxy, timeout=self.timeout)
        
        # Set user agent if rotation is enabled
        if self.user_agent_manager:
            user_agent = self.user_agent_manager.get_random_user_agent()
            engine = self._set_user_agent(engine, user_agent, engine_name)
        
        return engine
    
    def create_multi_engine(self, engines, ignore_duplicates: bool = True):
        """
        Create a MultipleSearchEngines instance.
        
        Args:
            engines: List of engine names to include
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            MultipleSearchEngines instance
        """
        logger.debug(f"Creating MultipleSearchEngines instance with: {engines}")
        
        multi_engine = MultipleSearchEngines(
            engines, 
            proxy=self.proxy,
            timeout=self.timeout,
            ignore_duplicate_urls=ignore_duplicates
        )
        
        # Set user agent for multi-engine if rotation is enabled
        if self.user_agent_manager:
            user_agent = self.user_agent_manager.get_random_user_agent()
            multi_engine = self._set_user_agent(multi_engine, user_agent, "multi_engine")
        
        return multi_engine
    
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