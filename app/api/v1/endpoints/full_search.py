from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from app.schemas.search import FullSearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/full-search", response_model=SearchResponse, summary="Full search with name and domain")
async def full_search(
    request: FullSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Perform a comprehensive search for a person at a specific company domain.
    
    This endpoint accepts a person's full name and a company domain and searches for
    relevant information across multiple search engines. It constructs complex search
    queries with various email patterns to find the most relevant information.
    
    - **full_name**: Person's full name to search for (required)
    - **domain**: Company domain to search for (required)
    - **engines**: Optional list of search engines to use (defaults to all available)
    - **pages**: Number of result pages to retrieve (default: 1)
    - **ignore_duplicates**: Whether to ignore duplicate URLs in results (default: true)
    - **use_proxy**: Whether to use a proxy for search requests (default: false)
    
    Returns structured search results grouped by search engine and combined unique results.
    """
    try:
        logger.info(f"Full search request received for: {request.full_name} at {request.domain}")
        
        # Use specified engines or default ones
        engines = request.engines or settings.DEFAULT_SEARCH_ENGINES
        
        # Create search service 
        search_service = SearchService(
            engines=engines,
            use_proxy=request.use_proxy or settings.USE_PROXY
        )
        
        # Perform the search
        results = search_service.full_search(
            full_name=request.full_name,
            domain=request.domain,
            pages=min(request.pages, settings.MAX_SEARCH_PAGES),
            ignore_duplicates=request.ignore_duplicates
        )
        
        return JSONResponse(content=results)
        
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error in full search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error in full search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the search operation") 