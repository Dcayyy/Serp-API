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
from app.utils.proxy_manager import ProxyManager
from app.utils.throttle import RequestThrottler

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for performing search operations.
    This is the main entry point for all search functionality.
    """
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        proxy_manager: Optional[ProxyManager] = None,
        timeout: int = settings.SEARCH_TIMEOUT,
        use_concurrent: bool = True,
        max_workers: int = settings.MAX_CONCURRENT_SEARCHES,
    ):
        """
        Initialize the search service.
        
        Args:
            proxy: Proxy URL to use for requests (if not using proxy rotation)
            proxy_manager: ProxyManager for proxy rotation (created if None)
            timeout: Request timeout in seconds
            use_concurrent: Whether to use concurrent execution (default: True)
            max_workers: Maximum number of concurrent workers (default: 10)
        """
        self.timeout = timeout
        self.use_concurrent = use_concurrent
        self.max_workers = max_workers
        
        # Set up proxy management
        self.proxy_manager = proxy_manager or ProxyManager([proxy] if proxy else None)
        self.fixed_proxy = proxy

        # Ensure output directory exists
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        # Create engine factory with proxy callback
        self.engine_factory = SearchEngineFactory(
            proxy=self.fixed_proxy,
            proxy_manager=self.proxy_manager,
            timeout=timeout,
            get_proxy_callback=self.get_proxy_for_engine
        )
        
        # Create throttler with engine-specific delays
        throttler = RequestThrottler(
            min_delay=settings.MIN_REQUEST_DELAY,
            max_delay=settings.MAX_REQUEST_DELAY,
            use_random_delays=settings.USE_RANDOM_DELAYS,
            engine_specific_delays=settings.ENGINE_SPECIFIC_DELAYS
        )
        
        # Create search executor
        logger.info(f"Initializing search service with{'out' if not use_concurrent else ''} concurrent execution")
        if use_concurrent:
            logger.info(f"Using concurrent search executor with {max_workers} workers")
            self.search_executor = ConcurrentSearchExecutor(
                engine_factory=self.engine_factory, 
                throttler=throttler,
                max_workers=max_workers
            )
        else:
            logger.info(f"Using sequential search executor")
            self.search_executor = SearchExecutor(
                engine_factory=self.engine_factory,
                throttler=throttler
            )
        
        # Initialize result processor
        self.result_processor = ResultProcessor(instance_id=settings.INSTANCE_ID)
        
        # Initialize strategies
        self.domain_strategy = DomainSearchStrategy(self.search_executor, self.result_processor)
        self.company_strategy = CompanySearchStrategy(self.search_executor, self.result_processor)
        self.full_strategy = FullSearchStrategy(self.search_executor, self.result_processor)
        
        logger.debug(f"SearchService initialized with proxy manager ({len(self.proxy_manager.proxies)} proxies), timeout: {timeout}s")
    
    def get_proxy_for_engine(self, engine_name: str) -> Optional[str]:
        """
        Get an appropriate proxy for the specific search engine.
        
        Args:
            engine_name: The search engine name
            
        Returns:
            Proxy URL or None if no proxies available
        """
        # If using a fixed proxy, return that
        if self.fixed_proxy:
            return self.fixed_proxy
            
        # Otherwise, get a proxy from the rotation
        return self.proxy_manager.get_proxy(preferred_engine=engine_name)
    
    def handle_request_error(self, proxy: str, engine_name: str, error: Exception) -> None:
        """
        Handle a request error that might be due to rate limiting.
        
        Args:
            proxy: The proxy that was used
            engine_name: The search engine that was queried
            error: The exception that occurred
        """
        logger.warning(f"Error with {engine_name} using proxy {proxy}: {str(error)}")
        
        # Mark the proxy as having an error
        if proxy and self.proxy_manager:
            self.proxy_manager.mark_proxy_error(proxy, engine_name)
    
    def handle_request_success(self, proxy: str) -> None:
        """
        Handle a successful request.
        
        Args:
            proxy: The proxy that was used
        """
        # Mark the proxy as successful
        if proxy and self.proxy_manager:
            self.proxy_manager.mark_proxy_success(proxy)
    
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