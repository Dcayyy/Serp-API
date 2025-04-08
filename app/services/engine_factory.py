from typing import Optional
import logging
from search_engines import Google, Bing, Yahoo, Duckduckgo
from search_engines.multiple_search_engines import MultipleSearchEngines

logger = logging.getLogger(__name__)

# Engine mapping for easier instantiation
ENGINE_MAPPING = {
    "google": Google,
    "bing": Bing,
    "yahoo": Yahoo,
    "duckduckgo": Duckduckgo
}


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
        logger.debug(f"EngineFactory initialized with proxy: {proxy or 'None'}, timeout: {timeout}s")
    
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
        return engine_class(proxy=self.proxy, timeout=self.timeout)
    
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
        return MultipleSearchEngines(
            engines, 
            proxy=self.proxy,
            timeout=self.timeout,
            ignore_duplicate_urls=ignore_duplicates
        ) 