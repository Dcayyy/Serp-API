from typing import Dict, Any, List, Optional
import logging
import time
import traceback
import concurrent.futures
from threading import Lock

from app.services.engine_factory import EngineFactory

logger = logging.getLogger(__name__)


class ConcurrentSearchExecutor:
    """Class for executing search operations across engines concurrently."""
    
    def __init__(self, engine_factory: EngineFactory, max_workers: int = 5):
        """
        Initialize the concurrent search executor.
        
        Args:
            engine_factory: Factory for creating search engine instances
            max_workers: Maximum number of concurrent workers (default: 5)
        """
        self.engine_factory = engine_factory
        self.max_workers = max_workers
        self.result_lock = Lock()  # Lock for thread-safe result updates
        logger.debug(f"ConcurrentSearchExecutor initialized with max_workers: {max_workers}")
    
    def execute_search(self, 
                      query: str, 
                      engines: List[str], 
                      pages: int = 1, 
                      ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Execute a search across specified engines concurrently.
        
        Args:
            query: Search query to execute
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict mapping engine names to their search results
        """
        engine_results = {}
        
        logger.info(f"Starting concurrent search across {len(engines)} engines")
        logger.debug(f"Query: {query}")
        
        # Use ThreadPoolExecutor to run searches in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, len(engines))) as executor:
            # Submit all search tasks
            future_to_engine = {
                executor.submit(
                    self._search_with_engine, 
                    engine_name, 
                    query, 
                    pages, 
                    ignore_duplicates
                ): engine_name 
                for engine_name in engines
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_engine):
                engine_name = future_to_engine[future]
                try:
                    result = future.result()
                    if result:
                        with self.result_lock:
                            engine_results[engine_name] = result
                            
                except Exception as e:
                    logger.error(f"Error in concurrent search for {engine_name}: {str(e)}")
                    logger.debug(traceback.format_exc())
        
        logger.info(f"Completed concurrent search across {len(engines)} engines, got {len(engine_results)} results")
        return engine_results
    
    def _search_with_engine(self, engine_name: str, query: str, pages: int, ignore_duplicates: bool) -> Optional[Any]:
        """
        Execute a search on a single engine (used for concurrent execution).
        
        Args:
            engine_name: Name of the search engine to use
            query: Search query to execute
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Search results or None if search failed
        """
        logger.info(f"Starting search on {engine_name}")
        
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
    
    def execute_multiple_searches(self, 
                                 queries: Dict[str, str],
                                 engines: List[str],
                                 pages: int = 1,
                                 ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Execute multiple different search queries concurrently.
        
        Args:
            queries: Dictionary mapping engine names to search queries
            engines: List of available search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict mapping engine names to their search results
        """
        engine_results = {}
        
        logger.info(f"Starting concurrent multi-query search with {len(queries)} queries")
        
        # Use ThreadPoolExecutor to run searches in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, len(queries))) as executor:
            # Submit all search tasks with the specified queries per engine
            future_to_engine = {}
            
            # Assign each query to an engine, fallback to the first engine if not enough engines
            for i, (engine_key, query) in enumerate(queries.items()):
                engine_name = engines[i % len(engines)] if i < len(engines) else engines[0]
                
                future = executor.submit(
                    self._search_with_engine, 
                    engine_name, 
                    query, 
                    pages, 
                    ignore_duplicates
                )
                
                future_to_engine[future] = (engine_key, engine_name)
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_engine):
                engine_key, engine_name = future_to_engine[future]
                try:
                    result = future.result()
                    if result:
                        with self.result_lock:
                            engine_results[engine_key] = result
                            
                except Exception as e:
                    logger.error(f"Error in concurrent search for {engine_key} using {engine_name}: {str(e)}")
                    logger.debug(traceback.format_exc())
        
        logger.info(f"Completed concurrent multi-query search, got {len(engine_results)} results")
        return engine_results 