from typing import Dict, Any, List, Optional
import logging

from app.utils.query_builder import (
    build_company_search_query,
    build_company_website_query
)
from app.services.strategies.search_strategy import SearchStrategy
from app.services.concurrent_search_executor import ConcurrentSearchExecutor

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
        Execute a company search.
        
        This performs two different searches concurrently:
        1. A generic search for the company name
        2. A search specifically for the company's official website
        
        Results from both searches are aggregated.
        
        Args:
            company_name: The company name to search for
            engines: List of search engines to use
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing aggregated search results in standardized format
        """
        logger.info(f"Performing concurrent company search for {company_name}")
        
        # Use only up to 2 search engines as specified
        engines_to_use = engines[:2] if len(engines) > 2 else engines
        
        # Prepare the queries
        query1 = build_company_search_query(company_name)
        query2 = build_company_website_query(company_name)
        
        logger.debug(f"Query 1: {query1}")
        logger.debug(f"Query 2: {query2}")
        
        # Check if the concurrent executor is available
        if hasattr(self.search_executor, 'execute_multiple_searches') and isinstance(self.search_executor, ConcurrentSearchExecutor):
            # If we have a concurrent executor, execute both searches in parallel
            queries = {
                f"{engines_to_use[0]}_info": query1,
                f"{engines_to_use[-1]}_website": query2
            }
            
            results_combined = self.search_executor.execute_multiple_searches(
                queries=queries,
                engines=engines_to_use,
                pages=pages,
                ignore_duplicates=ignore_duplicates
            )
        else:
            # Fall back to sequential execution if concurrent executor is not available
            logger.warning("Concurrent executor not available, falling back to sequential execution")
            results_combined = {}
            
            # First search with first engine
            if engines_to_use:
                engine1 = engines_to_use[0]
                logger.info(f"Using {engine1} for the first search")
                
                results = self.search_executor.execute_single_search(
                    query=query1,
                    engine_name=engine1,
                    pages=pages,
                    ignore_duplicates=ignore_duplicates
                )
                
                if results:
                    results_combined[engine1] = results
            
            # Second search with second engine
            if len(engines_to_use) > 1:
                engine2 = engines_to_use[1]
                logger.info(f"Using {engine2} for the second search")
                
                results = self.search_executor.execute_single_search(
                    query=query2,
                    engine_name=engine2,
                    pages=pages,
                    ignore_duplicates=ignore_duplicates
                )
                
                if results:
                    results_combined[engine2] = results
        
        # Process and combine results
        if not results_combined:
            logger.warning("No results from any search engine")
            return self.result_processor.create_empty_result(
                query=f"{query1} AND {query2}",
                engines=engines_to_use,
                error_message="No results from any search engine"
            )
        
        # Process the combined results using a descriptive query
        combined_query = f"Multiple queries for {company_name}"
        return self.result_processor.process_results(results_combined, combined_query) 