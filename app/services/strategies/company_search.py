from typing import Dict, Any, List
import logging
import time

from app.utils.query_builder import (
    build_company_name_query, 
    build_company_website_query
)
from app.services.strategies.search_strategy import SearchStrategy
from app.services.concurrent_search_executor import ConcurrentSearchExecutor
from app.schemas.search import SearchQuery

logger = logging.getLogger(__name__)


class CompanySearchStrategy(SearchStrategy):
    """Strategy for searching by company name."""
    
    def execute(
        self,
        company_name: str,
        engines: List[str],
        pages: int = 1,
        ignore_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a comprehensive company search strategy.
        
        This performs two different searches concurrently:
        1. A direct search for the company name
        2. A search for the company website using "site:" operator
        
        Args:
            company_name: The company name to search for
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in standardized format
        """
        start_time = time.time()
        logger.info(f"Performing concurrent company search for {company_name}")
        
        # Build the search queries
        name_query_str = build_company_name_query(company_name)
        website_query_str = build_company_website_query(company_name)
        
        logger.debug(f"Name query: {name_query_str}")
        logger.debug(f"Website query: {website_query_str}")
        
        # Create SearchQuery objects
        name_query = SearchQuery(query=name_query_str, page=pages)
        website_query = SearchQuery(query=website_query_str, page=pages)
        
        # Check if the concurrent executor is available
        if hasattr(self.search_executor, 'execute_multiple_searches') and isinstance(self.search_executor, ConcurrentSearchExecutor):
            # If we have a concurrent executor, execute both searches in parallel
            logger.info("Using concurrent multi-query search")
            queries = [name_query, website_query]
            
            results = self.search_executor.execute_multiple_searches(
                queries=queries,
                engines=engines,
                filter_duplicates=ignore_duplicates
            )
            
            name_results = results.get(name_query_str, {})
            website_results = results.get(website_query_str, {})
        else:
            # Fall back to sequential execution if concurrent executor is not available
            logger.warning("Concurrent executor not available, falling back to sequential execution")
            
            # Execute both searches sequentially
            name_results = self.search_executor.execute_search(
                query=name_query,
                engines=engines,
                filter_duplicates=ignore_duplicates
            )
            
            website_results = self.search_executor.execute_search(
                query=website_query,
                engines=engines,
                filter_duplicates=ignore_duplicates
            )
        
        # Combine the results for processing
        combined_results = {
            "company_name": name_results,
            "company_website": website_results
        }
        
        duration = time.time() - start_time
        logger.info(f"Company search completed in {duration:.2f}s")
        
        if not name_results and not website_results:
            logger.warning("No results from any search")
            return self.result_processor.create_empty_result(
                query=f"{name_query_str} & {website_query_str}",
                engines=engines
            )
        
        return self.result_processor.process_company_results(combined_results) 