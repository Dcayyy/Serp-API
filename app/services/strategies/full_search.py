from typing import Dict, Any, List
import logging

from app.utils.query_builder import build_full_search_query
from app.services.strategies.search_strategy import SearchStrategy
from app.services.concurrent_search_executor import ConcurrentSearchExecutor

logger = logging.getLogger(__name__)


class FullSearchStrategy(SearchStrategy):
    """Strategy for searching by a person's full name and domain."""
    
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
            full_name: The person's name to search for
            domain: The domain to search for
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in standardized format
        """
        query = build_full_search_query(full_name, domain)
        logger.info(f"Performing concurrent full search for {full_name} at {domain}")
        logger.debug(f"Generated query: {query}")
        
        # Check if the concurrent executor is available
        if hasattr(self.search_executor, 'execute_search') and isinstance(self.search_executor, ConcurrentSearchExecutor):
            # If we have a concurrent executor, execute the search concurrently
            engine_results = self.search_executor.execute_search(
                query=query,
                engines=engines,
                pages=pages,
                ignore_duplicates=ignore_duplicates
            )
        else:
            # Fall back to sequential execution if concurrent executor is not available
            logger.warning("Concurrent executor not available, falling back to sequential execution")
            # Execute search across all engines sequentially
            engine_results = self.search_executor.execute_search(
                query=query,
                engines=engines,
                pages=pages,
                ignore_duplicates=ignore_duplicates
            )
        
        # Process results or return empty result
        if not engine_results:
            logger.warning("No results from any search engine")
            return self.result_processor.create_empty_result(
                query=query,
                engines=engines
            )
        
        return self.result_processor.process_results(engine_results, query) 