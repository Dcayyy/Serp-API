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
    build_company_search_query,
    build_company_website_query
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
                titles = results.titles() if hasattr(results, 'titles') else []
                links = results.links() if hasattr(results, 'links') else []
                texts = results.text() if hasattr(results, 'text') else []
                
                logger.debug(f"{engine_name} returned {len(links)} links")
                
                engine_result_items = []
                for i in range(min(len(links), settings.SEARCH_RESULTS_LIMIT)):
                    if i < len(links) and i < len(titles) and i < len(texts):
                        item = {
                            "title": titles[i] if titles[i] else "No title",
                            "url": links[i],
                            "description": texts[i] if texts[i] else "No description"
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
                
                # Save raw results for debugging only if output method exists
                try:
                    if hasattr(results, 'output'):
                        output_dir = f"{settings.OUTPUT_DIR}/debug"
                        os.makedirs(output_dir, exist_ok=True)
                        output_file = f"{output_dir}/{engine_name}_{timestamp}"
                        results.output("json", output_file)
                        logger.debug(f"Saved raw {engine_name} results to {output_file}.json")
                    else:
                        logger.debug(f"{engine_name} results don't have output method, skipping debug save")
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
        
        This method performs two different searches:
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
        logger.info(f"Performing company search for {company_name}")
        
        # Use only up to 2 search engines as specified
        engines_to_use = self.engines[:2] if len(self.engines) > 2 else self.engines
        results_combined = {}
        
        # 1. First search: regular company search
        query1 = build_company_search_query(company_name)
        logger.debug(f"Query 1: {query1}")
        
        # First search handling with better error handling
        if engines_to_use:
            engine1 = engines_to_use[0]
            logger.info(f"Using {engine1} for the first search")
            
            try:
                engine_instance = self._create_engine_instance(engine1)
                engine_instance.ignore_duplicate_urls = ignore_duplicates
                
                # Execute search
                logger.debug(f"Executing {engine1} search for: {query1}")
                start_time = time.time()
                engine_instance.search(query1, pages)
                end_time = time.time()
                
                # Store results with extra validation for Google
                results = engine_instance.results
                
                # Add extra validation for Google which can sometimes have index issues
                if engine1 == 'google':
                    try:
                        # Validate results before processing
                        print(results)
                        titles = results.titles() if hasattr(results, 'titles') else []
                        links = results.links() if hasattr(results, 'links') else []
                        texts = results.text() if hasattr(results, 'text') else []
                        
                        # Ensure all arrays have the same length to prevent index errors
                        min_length = min(len(titles), len(links), len(texts))
                        logger.debug(f"{engine1} result lengths - titles: {len(titles)}, links: {len(links)}, texts: {len(texts)}")
                        
                        if min_length > 0:
                            logger.info(f"{engine1} search completed in {end_time - start_time:.2f}s, found {min_length} valid results")
                            results_combined[engine1] = results
                        else:
                            logger.warning(f"{engine1} search returned no valid results")
                    except Exception as e:
                        logger.error(f"Error validating {engine1} results: {str(e)}")
                        logger.debug(traceback.format_exc())
                else:
                    # For other engines, proceed as normal
                    links = results.links() if hasattr(results, 'links') else []
                    logger.info(f"{engine1} search completed in {end_time - start_time:.2f}s, found {len(links)} results")
                    results_combined[engine1] = results
                
                # Add delay between searches
                delay = 2  # 2 seconds between searches
                logger.debug(f"Waiting {delay}s before second search")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error searching with {engine1}: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # 2. Second search: official website search with different engine if available
        query2 = build_company_website_query(company_name)
        logger.debug(f"Query 2: {query2}")
        
        # Select second engine for second search
        if len(engines_to_use) > 1:
            engine2 = engines_to_use[1]
            logger.info(f"Using {engine2} for the second search")
            
            try:
                engine_instance = self._create_engine_instance(engine2)
                engine_instance.ignore_duplicate_urls = ignore_duplicates
                
                # Execute search
                logger.debug(f"Executing {engine2} search for: {query2}")
                start_time = time.time()
                engine_instance.search(query2, pages)
                end_time = time.time()
                
                # Store results with extra validation
                results = engine_instance.results
                
                # Add extra validation for Google which can sometimes have index issues
                if engine2 == 'google':
                    try:
                        # Validate results before processing
                        titles = results.titles() if hasattr(results, 'titles') else []
                        links = results.links() if hasattr(results, 'links') else []
                        texts = results.text() if hasattr(results, 'text') else []
                        
                        # Ensure all arrays have the same length to prevent index errors
                        min_length = min(len(titles), len(links), len(texts))
                        logger.debug(f"{engine2} result lengths - titles: {len(titles)}, links: {len(links)}, texts: {len(texts)}")
                        
                        if min_length > 0:
                            logger.info(f"{engine2} search completed in {end_time - start_time:.2f}s, found {min_length} valid results")
                            results_combined[engine2] = results
                        else:
                            logger.warning(f"{engine2} search returned no valid results")
                    except Exception as e:
                        logger.error(f"Error validating {engine2} results: {str(e)}")
                        logger.debug(traceback.format_exc())
                else:
                    # For other engines, proceed as normal
                    links = results.links() if hasattr(results, 'links') else []
                    logger.info(f"{engine2} search completed in {end_time - start_time:.2f}s, found {len(links)} results")
                    results_combined[engine2] = results
                
            except Exception as e:
                logger.error(f"Error searching with {engine2}: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Process and combine results
        if not results_combined:
            logger.warning("No results from any search engine")
            return {
                "query": f"{query1} AND {query2}",
                "results_by_engine": [],
                "combined_results": [],
                "total_results": 0,
                "metadata": {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "instance_id": self.instance_id,
                    "engines_used": engines_to_use,
                    "search_time": datetime.now().isoformat(),
                    "error": "No results from any search engine",
                    "query": f"{query1} AND {query2}"
                }
            }
        
        # Process the combined results using a descriptive query
        combined_query = f"Multiple queries for {company_name}"
        return self._process_results(results_combined, combined_query)
    
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