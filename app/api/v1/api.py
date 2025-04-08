from fastapi import APIRouter

from app.api.v1.endpoints import domain_search, full_search, company_search, simple_search

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(domain_search.router, prefix="/search", tags=["search"])
api_router.include_router(full_search.router, prefix="/search", tags=["search"])
api_router.include_router(company_search.router, prefix="/search", tags=["search"])
api_router.include_router(simple_search.router, prefix="/search", tags=["search"]) 