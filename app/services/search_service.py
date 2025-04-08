from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import os
import time
import traceback

from search_engines import Google, Bing, Yahoo, Duckduckgo
from search_engines.multiple_search_engines import MultipleSearchEngines

from app.core.config import settings
from app.utils.query_builder import (
    build_domain_query,
    build_full_search_query,
    build_company_search_query
)

logger = logging.getLogger(__name__)

# Engine mapping for easier instantiation
ENGINE_MAPPING = {
    "google": Google,
    "bing": Bing,
    "yahoo": Yahoo,
    "duckduckgo": Duckduckgo
}


class SearchService:
    """Service to handle search operations using search engines."""
    
    def __init__(
        self,
        engines: Optional[List[str]] = None,
        use_proxy: bool = False,
        timeout: int = settings.SEARCH_TIMEOUT,
        instance_id: str = settings.INSTANCE_ID
    ):
        """
        Initialize the search service.
        
        Args:
            engines: List of search engine names to use
            use_proxy: Whether to use a proxy
            timeout: Request timeout in seconds
            instance_id: Unique ID for this service instance (for distributed setups)
        """
        self.engines = engines or settings.DEFAULT_SEARCH_ENGINES
        self.proxy = settings.PROXY_URL if use_proxy else None
        self.timeout = timeout
        self.instance_id = instance_id
        
        # Ensure output directory exists
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        logger.info(f"SearchService initialized with engines: {self.engines}")
        logger.info(f"Proxy: {self.proxy or 'None'}, Timeout: {self.timeout}s")
    
    def _create_engine_instance(self, engine_name: str):
        """Create a search engine instance by name."""
        logger.debug(f"Creating {engine_name} search engine instance")
        
        if engine_name not in ENGINE_MAPPING:
            logger.error(f"Unsupported search engine: {engine_name}")
            raise ValueError(f"Unsupported search engine: {engine_name}")
        
        engine_class = ENGINE_MAPPING[engine_name]
        return engine_class(proxy=self.proxy, timeout=self.timeout)
    
    def _create_multi_engine(self, engines: List[str], ignore_duplicates: bool = True):
        """Create a MultipleSearchEngines instance."""
        logger.debug(f"Creating MultipleSearchEngines instance with: {engines}")
        return MultipleSearchEngines(engines, 
                                     proxy=self.proxy,
                                     timeout=self.timeout,
                                     ignore_duplicate_urls=ignore_duplicates)
    
    def _process_results(self, engine_results, query: str) -> Dict[str, Any]:
        """Process search results into a standardized format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_by_engine = []
        combined_results = []
        total_count = 0
        
        logger.debug(f"Processing results from {len(engine_results)} engines")
        
        # Process individual engine results
        for engine_name, results in engine_results.items():
            try:
                titles = results.titles()
                links = results.links()
                texts = results.text()
                
                logger.debug(f"{engine_name} returned {len(links)} links")
                
                engine_result_items = []
                for i in range(min(len(links), settings.SEARCH_RESULTS_LIMIT)):
                    if i < len(links):
                        item = {
                            "title": titles[i] if i < len(titles) else "No title",
                            "url": links[i],
                            "description": texts[i] if i < len(texts) else "No description"
                        }
                        engine_result_items.append(item)
                        
                        # Only add to combined results if not already there
                        if not any(r["url"] == links[i] for r in combined_results):
                            combined_results.append(item)
                
                results_by_engine.append({
                    "engine": engine_name,
                    "results": engine_result_items,
                    "total_results": len(links)
                })
                
                total_count += len(links)
                
                # Save raw results for debugging
                try:
                    output_dir = f"{settings.OUTPUT_DIR}/debug"
                    os.makedirs(output_dir, exist_ok=True)
                    output_file = f"{output_dir}/{engine_name}_{timestamp}"
                    results.output("json", output_file)
                    logger.debug(f"Saved raw {engine_name} results to {output_file}.json")
                except Exception as e:
                    logger.warning(f"Could not save debug output for {engine_name}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing results from {engine_name}: {str(e)}")
                logger.debug(traceback.format_exc())
                results_by_engine.append({
                    "engine": engine_name,
                    "results": [],
                    "total_results": 0,
                    "error": str(e)
                })
        
        # Create metadata
        metadata = {
            "timestamp": timestamp,
            "instance_id": self.instance_id,
            "engines_used": list(engine_results.keys()),
            "search_time": datetime.now().isoformat(),
            "query": query
        }
        
        logger.info(f"Search completed. Total results: {len(combined_results)}")
        
        return {
            "query": query,
            "results_by_engine": results_by_engine,
            "combined_results": combined_results,
            "total_results": len(combined_results),
            "metadata": metadata
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
        query = build_domain_query(domain)
        logger.info(f"Performing domain search for {domain}")
        logger.debug(f"Generated query: {query}")
        
        return self._perform_search(query, pages, ignore_duplicates)
    
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
        query = build_full_search_query(full_name, domain)
        logger.info(f"Performing full search for {full_name} at {domain}")
        logger.debug(f"Generated query: {query}")
        
        return self._perform_search(query, pages, ignore_duplicates)
    
    def search_by_company(self, company_name: str, pages: int = 1, ignore_duplicates: bool = True) -> Dict[str, Any]:
        """
        Search for a company name across multiple search engines.
        
        Args:
            company_name: The company name to search for
            pages: Number of result pages to retrieve
            ignore_duplicates: Whether to ignore duplicate URLs
            
        Returns:
            Dict containing search results in structured format
        """
        query = build_company_search_query(company_name)
        logger.info(f"Performing company search for {company_name}")
        logger.debug(f"Generated query: {query}")
        
        return self._perform_search(query, pages, ignore_duplicates)
    
    def _perform_search(self, query: str, pages: int = 1, ignore_duplicates: bool = True) -> Dict[str, Any]:
        """Execute search across all configured engines and process results."""
        engine_results = {}
        
        logger.info(f"Starting search across {len(self.engines)} engines")
        logger.debug(f"Query: {query}")
        logger.debug(f"Pages: {pages}, Ignore duplicates: {ignore_duplicates}")
        
        # Rate limiting to avoid detection
        remaining_engines = len(self.engines)
        for engine_name in self.engines:
            try:
                logger.info(f"Searching with {engine_name}...")
                
                engine = self._create_engine_instance(engine_name)
                engine.ignore_duplicate_urls = ignore_duplicates
                
                # Execute search
                logger.debug(f"Executing {engine_name} search for: {query}")
                start_time = time.time()
                engine.search(query, pages)
                end_time = time.time()
                
                # Store results
                results = engine.results
                links = results.links() if hasattr(results, 'links') else []
                
                logger.info(f"{engine_name} search completed in {end_time - start_time:.2f}s, found {len(links)} results")
                engine_results[engine_name] = engine.results
                
                # Implement rate limiting between requests
                remaining_engines -= 1
                if remaining_engines > 0:
                    delay = 2  # 2 seconds between engines
                    logger.debug(f"Waiting {delay}s before next engine")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error searching with {engine_name}: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Process and return results
        if not engine_results:
            logger.warning("No results from any search engine")
            return {
                "query": query,
                "results_by_engine": [],
                "combined_results": [],
                "total_results": 0,
                "metadata": {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "instance_id": self.instance_id,
                    "engines_used": self.engines,
                    "search_time": datetime.now().isoformat(),
                    "error": "No results from any search engine"
                }
            }
            
        return self._process_results(engine_results, query) 