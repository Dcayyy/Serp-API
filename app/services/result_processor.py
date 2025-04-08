from typing import Dict, Any, List
import logging
import os
from datetime import datetime
import traceback

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Class for processing search results into a standardized format."""
    
    def __init__(self, instance_id: str = "default"):
        """
        Initialize the result processor.
        
        Args:
            instance_id: Unique ID for this service instance
        """
        self.instance_id = instance_id
        logger.debug(f"ResultProcessor initialized with instance_id: {instance_id}")
    
    def process_results(self, engine_results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Process search results into a standardized format.
        
        Args:
            engine_results: Dictionary of search results by engine
            query: The search query used
            
        Returns:
            Dict containing processed search results in a standardized format
        """
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
                    # Make sure we only process items that have all three components
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
                    "total_results": len(engine_result_items)
                })
                
                total_count += len(engine_result_items)
                
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
    
    def create_empty_result(self, query: str, engines: List[str], error_message: str = "No results from any search engine") -> Dict[str, Any]:
        """
        Create an empty result structure when no search results are available.
        
        Args:
            query: The search query used
            engines: List of engines that were queried
            error_message: Optional custom error message
            
        Returns:
            Dict containing empty search results structure
        """
        return {
            "query": query,
            "results_by_engine": [],
            "combined_results": [],
            "total_results": 0,
            "metadata": {
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "instance_id": self.instance_id,
                "engines_used": engines,
                "search_time": datetime.now().isoformat(),
                "error": error_message
            }
        } 