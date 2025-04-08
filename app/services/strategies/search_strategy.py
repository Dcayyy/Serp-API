from abc import ABC, abstractmethod
from typing import Dict, Any, List

from app.services.search_executor import SearchExecutor
from app.services.result_processor import ResultProcessor


class SearchStrategy(ABC):
    """Abstract base class for search strategies."""
    
    def __init__(
        self, 
        search_executor: SearchExecutor, 
        result_processor: ResultProcessor
    ):
        """
        Initialize the search strategy.
        
        Args:
            search_executor: Executor for search operations
            result_processor: Processor for search results
        """
        self.search_executor = search_executor
        self.result_processor = result_processor
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the search strategy.
        
        Args:
            **kwargs: Strategy-specific parameters
            
        Returns:
            Dict containing search results in standardized format
        """
        pass 