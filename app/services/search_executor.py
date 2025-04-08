from typing import Dict, List, Optional, Set, Any
import logging
import time
from app.core.config import settings
from app.schemas.search import SearchQuery, SearchResult
from app.services.engine_factory import SearchEngineFactory
from app.utils.throttle import RequestThrottler

logger = logging.getLogger(__name__)

class SearchExecutor:
    """
    Class for executing search operations across different engines.
    """
    
    def __init__(
        self,
        engine_factory: Optional[SearchEngineFactory] = None,
        throttler: Optional[RequestThrottler] = None,
        max_results_per_engine: int = settings.SEARCH_RESULTS_LIMIT,
    ):
        """
        Initialize the search executor.
        
        Args:
            engine_factory: Factory for creating search engine instances
            throttler: Request throttler for limiting request rates
            max_results_per_engine: Maximum number of results to return per engine
        """
        self.engine_factory = engine_factory or SearchEngineFactory()
        self.throttler = throttler or RequestThrottler()
        self.max_results_per_engine = max_results_per_engine
        logger.debug(f"SearchExecutor initialized with throttler: {self.throttler}")
    
    def execute_search(
        self,
        query: SearchQuery,
        engines: Optional[List[str]] = None,
        filter_duplicates: bool = True,
    ) -> Dict[str, List[SearchResult]]:
        """
        Execute a search across multiple engines.
        
        Args:
            query: SearchQuery object containing the search parameters
            engines: List of engine names to use, or None for default engines
            filter_duplicates: Whether to filter duplicate results across engines
            
        Returns:
            Dictionary mapping engine names to lists of search results
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        logger.info(f"Executing search for '{query.query}' across engines: {engines}")
        
        results: Dict[str, List[SearchResult]] = {}
        seen_urls: Set[str] = set()
        
        start_time = time.time()
        for engine_name in engines:
            engine_start_time = time.time()
            
            # Apply throttling delay if needed (prevents rate limiting)
            self.throttler.throttle(engine_name)
            
            # Execute search on this engine
            engine_results = self.execute_single_engine_search(query, engine_name)
            
            # Filter duplicate results if requested
            if filter_duplicates:
                filtered_results = []
                for result in engine_results:
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        filtered_results.append(result)
                engine_results = filtered_results
            
            results[engine_name] = engine_results
            
            engine_duration = time.time() - engine_start_time
            logger.debug(f"Search on {engine_name} completed in {engine_duration:.2f}s with {len(engine_results)} results")
        
        total_duration = time.time() - start_time
        total_results = sum(len(results_list) for results_list in results.values())
        logger.info(f"Search completed in {total_duration:.2f}s with {total_results} total results")
        
        return results
    
    def execute_single_engine_search(
        self,
        query: SearchQuery,
        engine_name: str,
    ) -> List[SearchResult]:
        """
        Execute a search on a single engine.
        
        Args:
            query: SearchQuery object containing the search parameters
            engine_name: Name of the engine to use
            
        Returns:
            List of search results from the engine
        """
        try:
            # Get an engine instance from the factory
            engine = self.engine_factory.get_engine(engine_name)
            
            # Apply rate limiting before executing search
            self.throttler.throttle(engine_name)
            
            # Execute the search with standard parameters
            start_time = time.time()
            
            # Standard search engines package uses different parameter names
            results = engine.search(
                query.query,
                pages=query.page or 1
            )
            
            duration = time.time() - start_time
            logger.debug(f"Search on {engine_name} returned {len(results.links()) if hasattr(results, 'links') else 0} results in {duration:.2f}s")
            
            # Convert to SearchResult objects
            search_results = []
            if hasattr(results, 'results'):
                for item in results.results():
                    search_results.append(
                        SearchResult(
                            title=item.get('title', ''),
                            url=item.get('link', ''),
                            snippet=item.get('text', '')
                        )
                    )
            elif hasattr(results, 'links'):
                # Some engines only provide links
                for link in results.links():
                    search_results.append(
                        SearchResult(
                            title='',
                            url=link,
                            snippet=''
                        )
                    )
            
            # Limit number of results if needed
            return search_results[:self.max_results_per_engine]
            
        except Exception as e:
            logger.error(f"Error executing search on {engine_name}: {str(e)}")
            return []
    
    def get_estimated_execution_time(self, num_engines: int) -> float:
        """
        Estimate the execution time for a search across multiple engines.
        
        Args:
            num_engines: Number of engines to search
            
        Returns:
            Estimated execution time in seconds
        """
        avg_delay = (self.throttler.min_delay + self.throttler.max_delay) / 2 if self.throttler.use_random_delays else self.throttler.min_delay
        avg_search_time = 2.0  # Assume average search takes 2 seconds
        
        return num_engines * (avg_delay + avg_search_time) 