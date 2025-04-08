from typing import List, Dict, Any, Optional
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.services.engine_factory import SearchEngineFactory
from app.services.search_executor import SearchExecutor
from app.services.concurrent_search_executor import ConcurrentSearchExecutor
from app.services.result_processor import ResultProcessor
from app.services.strategies.company_search import CompanySearchStrategy
from app.services.strategies.domain_search import DomainSearchStrategy
from app.services.strategies.full_search import FullSearchStrategy
from app.schemas.search import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for performing search operations.
    This is the main entry point for all search functionality.
    """
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = settings.SEARCH_TIMEOUT,
        use_concurrent: bool = True,
        max_workers: int = settings.MAX_CONCURRENT_SEARCHES,
    ):
        """
        Initialize the search service.
        
        Args:
            proxy: Proxy URL to use for requests
            timeout: Request timeout in seconds
            use_concurrent: Whether to use concurrent execution (default: True)
            max_workers: Maximum number of concurrent workers (default: 5)
        """
        self.proxy = proxy
        self.timeout = timeout
        self.use_concurrent = use_concurrent
        self.max_workers = max_workers
        
        # Ensure output directory exists
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        # Create engine factory
        self.engine_factory = SearchEngineFactory(proxy=self.proxy, timeout=timeout)
        
        # Create search executor
        logger.info(f"Initializing search service with{'out' if not use_concurrent else ''} concurrent execution")
        if use_concurrent:
            logger.info(f"Using concurrent search executor with {max_workers} workers")
            self.search_executor = ConcurrentSearchExecutor(
                self.engine_factory, 
                max_workers=max_workers
            )
        else:
            logger.info(f"Using sequential search executor")
            self.search_executor = SearchExecutor(self.engine_factory)
        
        self.result_processor = ResultProcessor(instance_id=settings.INSTANCE_ID)
        
        # Initialize strategies
        self.company_strategy = CompanySearchStrategy(self.search_executor, self.result_processor)
        self.domain_strategy = DomainSearchStrategy(self.search_executor, self.result_processor)
        self.full_strategy = FullSearchStrategy(self.search_executor, self.result_processor)
        
        logger.debug(f"SearchService initialized with proxy: {proxy or 'None'}, timeout: {timeout}s")
    
    def get_supported_engines(self) -> List[str]:
        """
        Get a list of all supported search engines.
        
        Returns:
            List of supported engine names
        """
        return self.engine_factory.get_supported_engines()
    
    def execute_search(
        self, 
        query: str, 
        engines: Optional[List[str]] = None,
        page: int = 1,
        filter_duplicates: bool = True,
        **kwargs
    ) -> Dict[str, List[SearchResult]]:
        """
        Execute a search across multiple engines.
        
        Args:
            query: Search query string
            engines: List of engine names to use, or None for default engines
            page: Page number for search results
            filter_duplicates: Whether to filter duplicate results
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary mapping engine names to search results
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        logger.info(f"Executing search for '{query}' across: {engines}")
        
        # Create the search query object
        search_query = SearchQuery(
            query=query,
            page=page,
            **kwargs
        )
        
        # Execute the search
        return self.search_executor.execute_search(
            query=search_query,
            engines=engines,
            filter_duplicates=filter_duplicates
        )
    
    def execute_company_search(
        self, 
        company_name: str, 
        engines: Optional[List[str]] = None,
        page: int = 1,
        filter_duplicates: bool = True,
    ) -> Dict[str, Dict[str, List[SearchResult]]]:
        """
        Execute a company search strategy with multiple queries.
        
        This method performs two different searches concurrently:
        1. A direct search for the company name
        2. A search for the company website using "site:" operator
        
        Args:
            company_name: Company name to search for
            engines: List of engine names to use, or None for default engines
            page: Page number for search results
            filter_duplicates: Whether to filter duplicate results
            
        Returns:
            Dictionary mapping query types to search results by engine
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        logger.info(f"Executing company search for '{company_name}'")
        
        # Create multiple search queries
        queries = [
            SearchQuery(
                query=company_name,
                page=page
            ),
            SearchQuery(
                query=f"site:{company_name}.com",
                page=page
            )
        ]
        
        # Execute both searches (concurrently if supported)
        if hasattr(self.search_executor, 'execute_multiple_searches'):
            logger.debug("Using concurrent multi-query search")
            results = self.search_executor.execute_multiple_searches(
                queries=queries,
                engines=engines,
                filter_duplicates=filter_duplicates
            )
        else:
            # Fall back to sequential execution
            logger.debug("Using sequential multi-query search")
            results = {}
            for query in queries:
                results[query.query] = self.search_executor.execute_search(
                    query=query,
                    engines=engines,
                    filter_duplicates=filter_duplicates
                )
        
        return {
            "company_name": results.get(company_name, {}),
            "company_site": results.get(f"site:{company_name}.com", {})
        }
    
    def search_by_domain(self, domain: str, pages: int = 1, ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Search for a company domain across multiple search engines.
        
        Args:
            domain: The company domain to search for
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in structured format
        """
        return self.domain_strategy.execute(
            domain=domain,
            engines=self.get_supported_engines(),
            pages=pages,
            ignore_duplicates=ignore_duplicates
        )
    
    def full_search(self, full_name: str, domain: str, pages: int = 1, ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Search for a person's full name and company domain.
        
        Args:
            full_name: The person's name to search for
            domain: The company domain to search for
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in structured format
        """
        return self.full_strategy.execute(
            full_name=full_name,
            domain=domain,
            engines=self.get_supported_engines(),
            pages=pages,
            ignore_duplicates=ignore_duplicates
        )
    
    def search_by_company(self, company_name: str, pages: int = 1, ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Search for a company name across multiple search engines.
        
        This method performs two different searches concurrently:
        1. A generic search for the company name
        2. A search specifically for the company's official website
        
        Results from both searches are aggregated.
        
        Args:
            company_name: The company name to search for
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing aggregated search results in structured format
        """
        return self.company_strategy.execute(
            company_name=company_name,
            engines=self.get_supported_engines(),
            pages=pages,
            ignore_duplicates=ignore_duplicates
        ) 