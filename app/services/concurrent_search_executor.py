from typing import Dict, List, Optional, Set, Any
import logging
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.schemas.search import SearchQuery, SearchResult
from app.services.engine_factory import SearchEngineFactory
from app.utils.throttle import RequestThrottler

logger = logging.getLogger(__name__)


class ConcurrentSearchExecutor:
    """
    Class for executing search operations across engines concurrently using thread pool.
    This is especially useful for large numbers of engines or queries.
    """
    
    def __init__(
        self,
        engine_factory: Optional[SearchEngineFactory] = None,
        throttler: Optional[RequestThrottler] = None,
        max_workers: int = settings.MAX_CONCURRENT_SEARCHES,
        max_results_per_engine: int = settings.SEARCH_RESULTS_LIMIT,
    ):
        """
        Initialize the concurrent search executor.
        
        Args:
            engine_factory: Factory for creating search engine instances
            throttler: Request throttler for limiting request rates
            max_workers: Maximum number of concurrent workers
            max_results_per_engine: Maximum number of results to return per engine
        """
        self.engine_factory = engine_factory or SearchEngineFactory()
        self.throttler = throttler or RequestThrottler()
        self.max_workers = max_workers
        self.max_results_per_engine = max_results_per_engine
        self._result_lock = threading.Lock()
        logger.debug(f"ConcurrentSearchExecutor initialized with max {max_workers} workers and throttler: {self.throttler}")
    
    def execute_search(
        self,
        query: SearchQuery,
        engines: Optional[List[str]] = None,
        filter_duplicates: bool = True,
    ) -> Dict[str, List[SearchResult]]:
        """
        Execute a search across specified engines concurrently.
        
        Args:
            query: SearchQuery object containing the search parameters
            engines: List of engine names to use, or None for default engines
            filter_duplicates: Whether to filter duplicate results across engines
            
        Returns:
            Dictionary mapping engine names to lists of search results
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        threads = min(self.max_workers, len(engines))
        
        logger.info(f"Starting concurrent search for '{query.query}' across {len(engines)} engines with {threads} threads")
        
        results: Dict[str, List[SearchResult]] = {}
        seen_urls: Set[str] = set()
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # Create a thread-safe queue of engines to process
            engine_queue = queue.Queue()
            for engine_name in engines:
                engine_queue.put(engine_name)
            
            # Submit search tasks for each engine
            futures = []
            for _ in range(threads):
                future = executor.submit(
                    self._worker_search_engine,
                    query,
                    engine_queue,
                    results,
                    seen_urls,
                    filter_duplicates
                )
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in search worker thread: {str(e)}")
        
        # Filter results if needed and log summary
        total_results = sum(len(results_list) for results_list in results.values())
        logger.info(f"Concurrent search completed with {total_results} total results from {len(results)} engines")
        
        return results
    
    def _worker_search_engine(
        self,
        query: SearchQuery,
        engine_queue: queue.Queue,
        results: Dict[str, List[SearchResult]],
        seen_urls: Set[str],
        filter_duplicates: bool
    ):
        """
        Worker thread function that processes engines from the queue.
        
        Args:
            query: SearchQuery object containing the search parameters
            engine_queue: Queue of engine names to process
            results: Dict to store search results (thread-safe with lock)
            seen_urls: Set of seen URLs for deduplication (thread-safe with lock)
            filter_duplicates: Whether to filter duplicate results
        """
        while not engine_queue.empty():
            try:
                # Get the next engine to process
                engine_name = engine_queue.get_nowait()
                
                # Apply throttling before making the request
                self.throttler.throttle(engine_name)
                
                try:
                    # Execute search on this engine
                    engine_results = self.execute_single_engine_search(query, engine_name)
                    
                    # Store results (thread-safe)
                    with self._result_lock:
                        # Filter duplicate results if requested
                        if filter_duplicates:
                            filtered_results = []
                            for result in engine_results:
                                if result.url not in seen_urls:
                                    seen_urls.add(result.url)
                                    filtered_results.append(result)
                            engine_results = filtered_results
                        
                        results[engine_name] = engine_results
                        
                except Exception as e:
                    logger.error(f"Error executing search on {engine_name}: {str(e)}")
                
                # Mark this task as done
                engine_queue.task_done()
                
            except queue.Empty:
                # No more engines to process
                break
            except Exception as e:
                logger.error(f"Unexpected error in search worker: {str(e)}")
    
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
    
    def execute_multiple_searches(
        self,
        queries: List[SearchQuery],
        engines: Optional[List[str]] = None,
        filter_duplicates: bool = True
    ) -> Dict[str, Dict[str, List[SearchResult]]]:
        """
        Execute multiple search queries across specified engines.
        
        Args:
            queries: List of SearchQuery objects to execute
            engines: List of search engines to use, or None for default engines
            filter_duplicates: Whether to filter duplicate results
            
        Returns:
            Dict mapping query identifiers to engine results
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        threads = min(self.max_workers, len(queries))
        
        logger.info(f"Starting concurrent multi-query search: {len(queries)} queries, {len(engines)} engines")
        
        # Track results for each query
        query_results: Dict[str, Dict[str, List[SearchResult]]] = {}
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # Create a thread-safe queue of queries to process
            query_queue = queue.Queue()
            for query in queries:
                query_queue.put(query)
            
            # Submit search tasks for each query
            futures = []
            for _ in range(threads):
                future = executor.submit(
                    self._worker_search_query,
                    query_queue,
                    query_results,
                    engines,
                    filter_duplicates
                )
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in query worker thread: {str(e)}")
        
        return query_results
    
    def _worker_search_query(
        self,
        query_queue: queue.Queue,
        results: Dict[str, Dict[str, List[SearchResult]]],
        engines: List[str],
        filter_duplicates: bool
    ):
        """
        Worker thread function that processes queries from the queue.
        
        Args:
            query_queue: Queue of queries to process
            results: Dict to store search results (thread-safe with lock)
            engines: List of search engines to use
            filter_duplicates: Whether to filter duplicate results
        """
        while not query_queue.empty():
            try:
                # Get the next query to process
                query = query_queue.get_nowait()
                
                # Execute search for this query
                logger.debug(f"Thread executing search for query: {query.query}")
                start_time = time.time()
                
                try:
                    query_result = self.execute_search(query, engines, filter_duplicates)
                    
                    # Store results (thread-safe)
                    with self._result_lock:
                        # Use query string as key
                        results[query.query] = query_result
                    
                    end_time = time.time()
                    logger.info(f"Query '{query.query}' completed in {end_time - start_time:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Error during search for query '{query.query}': {str(e)}")
                
                # Mark this task as done
                query_queue.task_done()
                
            except queue.Empty:
                # No more queries to process
                break
            except Exception as e:
                logger.error(f"Unexpected error in query worker: {str(e)}")
    
    def get_estimated_execution_time(self, num_engines: int, num_queries: int = 1) -> float:
        """
        Estimate the execution time for a search across multiple engines.
        
        Args:
            num_engines: Number of engines to search
            num_queries: Number of queries to execute
            
        Returns:
            Estimated execution time in seconds
        """
        avg_delay = (self.throttler.min_delay + self.throttler.max_delay) / 2 if self.throttler.use_random_delays else self.throttler.min_delay
        avg_search_time = 2.0  # Assume average search takes 2 seconds
        
        # With concurrent execution, divide by number of workers
        effective_workers = min(self.max_workers, num_engines)
        
        # For multiple queries, consider the queue processing time
        if num_queries > 1:
            effective_workers = min(self.max_workers, num_queries)
            return (num_queries * num_engines * (avg_delay + avg_search_time)) / effective_workers
        else:
            return (num_engines * (avg_delay + avg_search_time)) / effective_workers 