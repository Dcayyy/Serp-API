from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
from pydantic import BaseModel, Field

from app.services.search_service import SearchService
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Request model for simple search
class SimpleSearchRequest(BaseModel):
    query: str = Field(..., description="The search query to execute")
    engines: Optional[List[str]] = Field(None, description="Search engines to use")
    pages: Optional[int] = Field(1, description="Number of pages to retrieve")
    ignore_duplicates: Optional[bool] = Field(True, description="Ignore duplicate results")
    use_proxy: Optional[bool] = Field(None, description="Whether to use proxy")

@router.post("/simple-search", summary="Simple search with custom query")
async def simple_search(
    request: SimpleSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Perform a search with a custom query string across multiple search engines.
    
    This endpoint accepts a simple search query string and returns results from various
    search engines, including titles, URLs, and descriptions of the results.
    
    - **query**: The search query to execute (required)
    - **engines**: Optional list of search engines to use (defaults to all available)
    - **pages**: Number of result pages to retrieve (default: 1)
    - **ignore_duplicates**: Whether to ignore duplicate URLs in results (default: true)
    - **use_proxy**: Whether to use a proxy for search requests (default: false)
    
    Returns structured search results grouped by search engine and combined unique results.
    """
    try:
        logger.info(f"Simple search request received: {request.query}")
        
        # Use specified engines or default ones
        engines = request.engines or settings.DEFAULT_SEARCH_ENGINES
        
        # Create search service 
        search_service = SearchService(
            engines=engines,
            use_proxy=request.use_proxy or settings.USE_PROXY
        )
        
        # Directly use the provided query
        results = search_service._perform_search(
            query=request.query,
            pages=min(request.pages, settings.MAX_SEARCH_PAGES),
            ignore_duplicates=request.ignore_duplicates
        )
        
        return JSONResponse(content=results)
        
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error in simple search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error in simple search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the search operation") 