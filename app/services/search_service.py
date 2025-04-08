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
        use_concurrent: bool = True,
        max_workers: int = settings.MAX_CONCURRENT_SEARCHES,
        max_results_per_engine: int = settings.SEARCH_RESULTS_LIMIT
    ):
        """
        Initialize the search service.
        
        Args:
            proxy: Optional proxy URL to use for requests
            use_concurrent: Whether to use concurrent execution
            max_workers: Maximum number of concurrent workers
            max_results_per_engine: Maximum number of results to return per engine
        """
        self.proxy = proxy
        self.use_concurrent = use_concurrent
        self.max_workers = max_workers
        self.max_results_per_engine = max_results_per_engine
        
        # Create the search engine factory
        self.engine_factory = SearchEngineFactory(proxy=proxy)
        
        # Create rate limiter for API requests
        self.throttler = RequestThrottler(
            min_delay=settings.MIN_REQUEST_DELAY,
            max_delay=settings.MAX_REQUEST_DELAY,
            use_random_delays=settings.USE_RANDOM_DELAYS
        )
        
        # Create result processor
        self.result_processor = ResultProcessor()
        
        # Create executor based on configuration
        if use_concurrent:
            self.executor = ConcurrentSearchExecutor(
                engine_factory=self.engine_factory,
                throttler=self.throttler,
                max_workers=max_workers,
                max_results_per_engine=max_results_per_engine
            )
        else:
            self.executor = SearchExecutor(
                engine_factory=self.engine_factory,
                throttler=self.throttler,
                max_results_per_engine=max_results_per_engine
            )
            
        logger.debug(f"Search service initialized with proxy={proxy}, concurrent={use_concurrent}")
        
    def set_proxy(self, proxy_url: Optional[str]):
        """
        Change the proxy settings for the search service.
        
        Args:
            proxy_url: New proxy URL to use, or None to disable
        """
        if self.proxy == proxy_url:
            return  # No change needed
            
        logger.debug(f"Updating search service proxy to: {proxy_url}")
        self.proxy = proxy_url
        
        # Update the engine factory with the new proxy
        self.engine_factory = SearchEngineFactory(proxy=proxy_url)
        
        # Update the executor with the new engine factory
        if self.use_concurrent:
            self.executor = ConcurrentSearchExecutor(
                engine_factory=self.engine_factory,
                throttler=self.throttler,
                max_workers=self.max_workers,
                max_results_per_engine=self.max_results_per_engine
            )
        else:
            self.executor = SearchExecutor(
                engine_factory=self.engine_factory,
                throttler=self.throttler,
                max_results_per_engine=self.max_results_per_engine
            )
    
    def get_proxy_for_engine(self, engine_name: str) -> Optional[str]:
        """
        Get an appropriate proxy for the specific search engine.
        
        Args:
            engine_name: The search engine name
            
        Returns:
            Proxy URL or None if no proxies available
        """
        # If using a fixed proxy, return that
        if self.proxy:
            return self.proxy
            
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
        return self.executor.execute_search(
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
        search_type_to_engine: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Dict[str, List[SearchResult]]]:
        """
        Execute a company search strategy with multiple queries.
        
        This method performs two different searches:
        1. A direct search for the company name on the first engine
        2. A search for the company website using "site:" operator on the second engine
        
        Each engine is assigned a specific query type to search for.
        
        Args:
            company_name: Company name to search for
            engines: List of engine names to use, or None for default engines
            page: Page number for search results
            filter_duplicates: Whether to filter duplicate results
            search_type_to_engine: Optional mapping of search types to specific engines
            
        Returns:
            Dictionary mapping query types to search results by engine
        """
        engines = engines or settings.DEFAULT_SEARCH_ENGINES
        logger.info(f"Executing company search for '{company_name}'")
        
        # Determine which engines to use for each search type
        name_engines = []
        website_engines = []
        
        if search_type_to_engine:
            # Use the provided mapping
            name_engines = search_type_to_engine.get("company_name", [engines[0] if engines else None])
            website_engines = search_type_to_engine.get("company_website", [engines[1] if len(engines) > 1 else engines[0]])
            logger.info(f"Using custom engine allocation: name search -> {name_engines}, website search -> {website_engines}")
        else:
            # Default allocation: first engine for name search, second for website search
            if engines:
                name_engines = [engines[0]]
                website_engines = [engines[1] if len(engines) > 1 else engines[0]]
                logger.info(f"Using default engine allocation: name search -> {name_engines}, website search -> {website_engines}")
        
        # Create search queries
        name_query = SearchQuery(
            query=company_name,
            page=page
        )
        
        website_query = SearchQuery(
            query=f"site:{company_name}.com",
            page=page
        )
        
        # Execute company name search on the first engine
        name_results = {}
        if name_engines:
            logger.debug(f"Executing company name search on engines: {name_engines}")
            name_results = self.executor.execute_search(
                query=name_query,
                engines=name_engines,
                filter_duplicates=filter_duplicates
            )
        
        # Execute company website search on the second engine
        website_results = {}
        if website_engines:
            logger.debug(f"Executing company website search on engines: {website_engines}")
            website_results = self.executor.execute_search(
                query=website_query,
                engines=website_engines,
                filter_duplicates=filter_duplicates
            )
        
        return {
            "company_name": name_results,
            "company_website": website_results
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