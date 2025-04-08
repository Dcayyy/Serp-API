from typing import List, Dict, Any, Optional
import logging
import os

from app.core.config import settings
from app.services.engine_factory import EngineFactory
from app.services.search_executor import SearchExecutor
from app.services.concurrent_search_executor import ConcurrentSearchExecutor
from app.services.result_processor import ResultProcessor
from app.services.strategies.company_search import CompanySearchStrategy
from app.services.strategies.domain_search import DomainSearchStrategy
from app.services.strategies.full_search import FullSearchStrategy

logger = logging.getLogger(__name__)


class SearchService:
    """Service to handle search operations using search engines."""
    
    def __init__(
        self,
        engines: Optional[List[str]] = None,
        use_proxy: bool = False,
        timeout: int = settings.SEARCH_TIMEOUT,
        instance_id: str = settings.INSTANCE_ID,
        use_concurrent: bool = True,
        max_workers: int = 5
    ):
        """
        Initialize the search service.
        
        Args:
            engines: List of search engine names to use
            use_proxy: Whether to use a proxy
            timeout: Request timeout in seconds
            instance_id: Unique ID for this service instance (for distributed setups)
            use_concurrent: Whether to use concurrent execution (default: True)
            max_workers: Maximum number of concurrent workers (default: 5)
        """
        self.engines = engines or settings.DEFAULT_SEARCH_ENGINES
        self.proxy = settings.PROXY_URL if use_proxy else None
        self.instance_id = instance_id
        self.use_concurrent = use_concurrent
        
        # Ensure output directory exists
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        # Initialize components
        self.engine_factory = EngineFactory(proxy=self.proxy, timeout=timeout)
        
        # Create appropriate search executor based on configuration
        if use_concurrent:
            logger.info(f"Using concurrent search executor with {max_workers} workers")
            self.search_executor = ConcurrentSearchExecutor(self.engine_factory, max_workers=max_workers)
        else:
            logger.info("Using sequential search executor")
            self.search_executor = SearchExecutor(self.engine_factory)
            
        self.result_processor = ResultProcessor(instance_id=instance_id)
        
        # Initialize strategies
        self.company_strategy = CompanySearchStrategy(self.search_executor, self.result_processor)
        self.domain_strategy = DomainSearchStrategy(self.search_executor, self.result_processor)
        self.full_strategy = FullSearchStrategy(self.search_executor, self.result_processor)
        
        logger.info(f"SearchService initialized with engines: {self.engines}")
        logger.info(f"Proxy: {self.proxy or 'None'}, Timeout: {timeout}s")
    
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
            engines=self.engines,
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
            engines=self.engines,
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
            engines=self.engines,
            pages=pages,
            ignore_duplicates=ignore_duplicates
        ) 