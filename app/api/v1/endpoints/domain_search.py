from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from app.schemas.search import DomainSearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.config import settings
from app.utils.query_builder import build_domain_query

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/by-domain", response_model=SearchResponse, summary="Search by domain")
async def search_by_domain(
    request: DomainSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Perform a search for a company domain across multiple search engines concurrently.
    
    This endpoint accepts a company domain and returns search results from various
    search engines, including titles, URLs, and descriptions of the results.
    Searches are executed in parallel for faster response times.
    
    - **domain**: Domain to search for (required)
    - **engines**: Optional list of search engines to use (defaults to all available)
    - **pages**: Number of result pages to retrieve (default: 1)
    - **ignore_duplicates**: Whether to ignore duplicate URLs in results (default: true)
    - **use_proxy**: Whether to use a proxy for search requests (default: false)
    
    Returns structured search results grouped by search engine and combined unique results.
    """
    try:
        logger.info(f"Domain search request received for: {request.domain}")
        
        # Use specified engines or default ones
        engines = request.engines or settings.DEFAULT_SEARCH_ENGINES
        
        # Create search service with concurrent execution
        search_service = SearchService(
            proxy=settings.PROXY_URL if request.use_proxy or settings.USE_PROXY else None,
            use_concurrent=settings.USE_CONCURRENT_SEARCH,
            max_workers=settings.MAX_CONCURRENT_SEARCHES
        )
        
        # Perform the search using domain search strategy
        query = build_domain_query(request.domain)
        
        results = search_service.execute_search(
            query=query,
            engines=engines,
            page=min(request.pages, settings.MAX_SEARCH_PAGES),
            filter_duplicates=request.ignore_duplicates
        )
        
        # Convert results to JSON-serializable format
        serializable_results = {
            "query": query,
            "results_by_engine": [],
            "combined_results": [],
            "total_results": 0,
            "metadata": {
                "domain": request.domain,
                "engines": engines,
                "pages": min(request.pages, settings.MAX_SEARCH_PAGES)
            }
        }
        
        # Process results by engine
        all_results = []
        for engine, search_results in results.items():
            engine_data = {
                "engine": engine,
                "results": [{"title": r.title, "url": r.url, "description": r.snippet} for r in search_results],
                "total_results": len(search_results)
            }
            serializable_results["results_by_engine"].append(engine_data)
            all_results.extend(search_results)
        
        # Add combined unique results
        seen_urls = set()
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                serializable_results["combined_results"].append({
                    "title": result.title, 
                    "url": result.url, 
                    "description": result.snippet
                })
        
        serializable_results["total_results"] = len(serializable_results["combined_results"])
        
        return JSONResponse(content=serializable_results)
        
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error in domain search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error in domain search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during the search operation") 