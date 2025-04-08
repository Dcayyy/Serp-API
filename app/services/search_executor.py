from typing import Dict, Any, List, Optional
import logging
import time
import traceback

from app.services.engine_factory import EngineFactory

logger = logging.getLogger(__name__)


class SearchExecutor:
    """Class for executing search operations across engines."""
    
    def __init__(self, engine_factory: EngineFactory):
        """
        Initialize the search executor.
        
        Args:
            engine_factory: Factory for creating search engine instances
        """
        self.engine_factory = engine_factory
        logger.debug("SearchExecutor initialized with engine factory")
    
    def execute_search(self, 
                      query: str, 
                      engines: List[str], 
                      pages: int = 1, 
                      ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Execute a search across specified engines.
        
        Args:
            query: Search query to execute
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict mapping engine names to their search results
        """
        engine_results = {}
        
        logger.info(f"Starting search across {len(engines)} engines")
        logger.debug(f"Query: {query}")
        logger.debug(f"Pages: {pages}, Ignore duplicates: {ignore_duplicates}")
        
        # Rate limiting to avoid detection
        remaining_engines = len(engines)
        for engine_name in engines:
            try:
                logger.info(f"Searching with {engine_name}...")
                
                engine = self.engine_factory.create_engine(engine_name)
                engine.ignore_duplicate_urls = ignore_duplicates
                
                # Execute search
                logger.debug(f"Executing {engine_name} search for: {query}")
                start_time = time.time()
                
                try:
                    engine.search(query, pages)
                    end_time = time.time()
                    
                    # Store results
                    results = engine.results
                    links = results.links() if hasattr(results, 'links') else []
                    
                    logger.info(f"{engine_name} search completed in {end_time - start_time:.2f}s, found {len(links)} results")
                    engine_results[engine_name] = engine.results
                except Exception as e:
                    logger.error(f"Error during {engine_name} search operation: {str(e)}")
                    logger.debug(traceback.format_exc())
                
                # Implement rate limiting between requests
                remaining_engines -= 1
                if remaining_engines > 0:
                    delay = 2  # 2 seconds between engines
                    logger.debug(f"Waiting {delay}s before next engine")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error setting up {engine_name} search: {str(e)}")
                logger.debug(traceback.format_exc())
                
        return engine_results
    
    def execute_single_search(self, 
                             query: str, 
                             engine_name: str, 
                             pages: int = 1, 
                             ignore_duplicates: bool = True) -> Optional[Any]:
        """
        Execute a search on a single engine.
        
        Args:
            query: Search query to execute
            engine_name: Name of the search engine to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Search results or None if search failed
        """
        logger.info(f"Executing search on {engine_name}")
        logger.debug(f"Query: {query}")
        
        try:
            engine = self.engine_factory.create_engine(engine_name)
            engine.ignore_duplicate_urls = ignore_duplicates
            
            # Execute search
            logger.debug(f"Executing {engine_name} search for: {query}")
            start_time = time.time()
            
            try:
                engine.search(query, pages)
                end_time = time.time()
                
                # Store results
                results = engine.results
                links = results.links() if hasattr(results, 'links') else []
                
                logger.info(f"{engine_name} search completed in {end_time - start_time:.2f}s, found {len(links)} results")
                return results
            except Exception as e:
                logger.error(f"Error during {engine_name} search operation: {str(e)}")
                logger.debug(traceback.format_exc())
                return None
                
        except Exception as e:
            logger.error(f"Error setting up {engine_name} search: {str(e)}")
            logger.debug(traceback.format_exc())
            return None 