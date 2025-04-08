from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

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
    
    This endpoint accepts a company name and returns search results from various
    search engines, including titles, URLs, and descriptions of the results.
    The search is optimized to find information about the company, its contacts,
    team members, and related information.
    
    - **company_name**: Company name to search for (required)
    - **engines**: Optional list of search engines to use (defaults to all available)
    - **pages**: Number of result pages to retrieve (default: 1)
    - **ignore_duplicates**: Whether to ignore duplicate URLs in results (default: true)
    - **use_proxy**: Whether to use a proxy for search requests (default: false)
    
    Returns structured search results grouped by search engine and combined unique results.
    """
    try:
        logger.info(f"Company search request received for: {request.company_name}")
        
        # Use specified engines or default ones
        engines = request.engines or settings.DEFAULT_SEARCH_ENGINES
        
        # Create search service 
        search_service = SearchService(
            engines=engines,
            use_proxy=request.use_proxy or settings.USE_PROXY
        )
        
        # Perform the search
        results = search_service.search_by_company(
            company_name=request.company_name,
            pages=min(request.pages, settings.MAX_SEARCH_PAGES),
            ignore_duplicates=request.ignore_duplicates
        )
        
        return JSONResponse(content=results)
        
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error in company search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error in company search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the search operation") 