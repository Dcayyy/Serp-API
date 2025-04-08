from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict
import logging
import random

from app.schemas.search import CompanySearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Create the search service once when the app starts
search_service = SearchService(
    proxy=settings.PROXY_URL if settings.USE_PROXY else None,
    use_concurrent=settings.USE_CONCURRENT_SEARCH,
    max_workers=settings.MAX_CONCURRENT_SEARCHES
)

# Dependency to get the search service
def get_search_service():
    return search_service


@router.post("/by-company-name", response_model=SearchResponse, summary="Search by company name")
async def search_by_company_name(
    request: CompanySearchRequest,
    background_tasks: BackgroundTasks,
    service: SearchService = Depends(get_search_service),
):
    """
    Perform a search for a company name across multiple search engines.
    
    This endpoint accepts a company name and performs two strategic searches:
    1. A general search for the company using the first engine with a query optimized to find company information
    2. A search specifically for the company's official website using the second engine
    
    Each search type is assigned to a different engine, for a total of 2 searches per API call.
    
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
        
        # Create a mapping for search types to engines
        # First engine for company name search, second engine for website search
        search_type_to_engine: Dict[str, List[str]] = {
            "company_name": [selected_engines[0]],
            "company_website": [selected_engines[1]] if len(selected_engines) > 1 else [selected_engines[0]]
        }
        
        logger.info(f"Search allocation: company_name -> {search_type_to_engine['company_name'][0]}, " 
                   f"company_website -> {search_type_to_engine['company_website'][0]}")
        
        # Use the injected search service, update proxy if needed for this specific request
        if request.use_proxy and not settings.USE_PROXY:
            service.set_proxy(settings.PROXY_URL)
        elif not request.use_proxy and settings.USE_PROXY:
            service.set_proxy(None)
        
        # Perform the search with the allocated engines for each search type
        results = service.execute_company_search(
            company_name=request.company_name,
            engines=selected_engines,
            page=min(request.pages, settings.MAX_SEARCH_PAGES),
            filter_duplicates=request.ignore_duplicates,
            search_type_to_engine=search_type_to_engine
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