from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
import random

from app.schemas.search import CompanySearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/by-company-name", response_model=SearchResponse, summary="Search by company name")
async def search_by_company_name(
    request: CompanySearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Perform a search for a company name across multiple search engines.
    
    This endpoint accepts a company name and performs two strategic searches concurrently:
    1. A general search for the company using the first engine with a query optimized to find company information
    2. A search specifically for the company's official website using the second engine (if available)
    
    Results from both searches are aggregated and returned in a unified format.
    
    - **company_name**: Company name to search for (required)
    - **engines**: Optional list of search engines to use (defaults to all available, but only 2 randomly selected engines will be used)
    - **pages**: Number of result pages to retrieve (default: 1)
    - **ignore_duplicates**: Whether to ignore duplicate URLs in results (default: true)
    - **use_proxy**: Whether to use a proxy for search requests (default: false)
    
    Returns structured search results grouped by search engine and combined unique results.
    """
    try:
        logger.info(f"Company search request received for: {request.company_name}")
        
        # Use specified engines or default ones
        available_engines = request.engines or settings.DEFAULT_SEARCH_ENGINES
        
        # Randomly select only 2 engines regardless of how many are available
        selected_engines = random.sample(
            available_engines, 
            min(2, len(available_engines))  # Ensure we don't try to sample more than available
        )
        
        logger.info(f"Randomly selected engines for this request: {selected_engines}")
        
        # Create search service with concurrent execution
        search_service = SearchService(
            proxy=settings.PROXY_URL if request.use_proxy or settings.USE_PROXY else None,
            use_concurrent=settings.USE_CONCURRENT_SEARCH,
            max_workers=settings.MAX_CONCURRENT_SEARCHES
        )
        
        # Perform the search with only the selected engines
        results = search_service.execute_company_search(
            company_name=request.company_name,
            engines=selected_engines,
            page=min(request.pages, settings.MAX_SEARCH_PAGES),
            filter_duplicates=request.ignore_duplicates
        )
        
        # Convert results to JSON-serializable format
        serializable_results = {}
        for query_type, engine_results in results.items():
            serializable_results[query_type] = {}
            for engine, search_results in engine_results.items():
                serializable_results[query_type][engine] = [
                    {"title": r.title, "url": r.url, "snippet": r.snippet} 
                    for r in search_results
                ]
        
        return JSONResponse(content=serializable_results)
        
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error in company search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error in company search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the search operation") 