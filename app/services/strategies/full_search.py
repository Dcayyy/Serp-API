from typing import Dict, Any, List
import logging
import time

from app.utils.query_builder import build_full_query
from app.services.strategies.search_strategy import SearchStrategy
from app.services.concurrent_search_executor import ConcurrentSearchExecutor
from app.schemas.search import SearchQuery

logger = logging.getLogger(__name__)


class FullSearchStrategy(SearchStrategy):
    """Strategy for a comprehensive full search with name and domain."""
    
    def execute(
        self,
        full_name: str,
        domain: str,
        engines: List[str],
        pages: int = 1,
        ignore_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a full search for a person and domain concurrently across multiple engines.
        
        Args:
            full_name: Full name of the person to search for
            domain: Domain to include in search
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in standardized format
        """
        start_time = time.time()
        query_str = build_full_query(full_name, domain)
        logger.info(f"Performing full search for {full_name} at {domain}")
        logger.debug(f"Generated query: {query_str}")
        
        # Create SearchQuery object
        search_query = SearchQuery(
            query=query_str,
            page=pages
        )
        
        # Check if the concurrent executor is available
        if hasattr(self.search_executor, 'execute_search') and isinstance(self.search_executor, ConcurrentSearchExecutor):
            # If we have a concurrent executor, execute the search concurrently
            logger.info("Using concurrent search execution")
            engine_results = self.search_executor.execute_search(
                query=search_query,
                engines=engines,
                filter_duplicates=ignore_duplicates
            )
        else:
            # Fall back to sequential execution if concurrent executor is not available
            logger.warning("Concurrent executor not available, falling back to sequential execution")
            # Execute search across all engines sequentially
            engine_results = self.search_executor.execute_search(
                query=search_query,
                engines=engines,
                filter_duplicates=ignore_duplicates
            )
        
        duration = time.time() - start_time
        logger.info(f"Full search completed in {duration:.2f}s")
        
        # Process results or return empty result
        if not engine_results:
            logger.warning("No results from any search engine")
            return self.result_processor.create_empty_result(
                query=query_str,
                engines=engines
            )
        
        return self.result_processor.process_results(engine_results, query_str) 