from typing import Dict, Any, List
import logging

from app.utils.query_builder import build_domain_query
from app.services.strategies.search_strategy import SearchStrategy
from app.services.concurrent_search_executor import ConcurrentSearchExecutor
from app.schemas.search import SearchQuery

logger = logging.getLogger(__name__)


class DomainSearchStrategy(SearchStrategy):
    """Strategy for searching by domain."""
    
    def execute(
        self,
        domain: str,
        engines: List[str],
        pages: int = 1,
        ignore_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a domain search concurrently across multiple engines.
        
        Args:
            domain: The domain to search for
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in standardized format
        """
        query_str = build_domain_query(domain)
        logger.info(f"Performing domain search for {domain}")
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
        
        # Process results or return empty result
        if not engine_results:
            logger.warning("No results from any search engine")
            return self.result_processor.create_empty_result(
                query=query_str,
                engines=engines
            )
        
        return self.result_processor.process_results(engine_results, query_str) 