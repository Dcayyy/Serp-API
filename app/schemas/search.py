from typing import List, Optional, Dict, Any
import re
import sys

# Check if we're using pydantic v1 or v2
try:
    # Attempt to import from pydantic v2
    from pydantic import field_validator as validator
    from pydantic import BaseModel, Field
    USING_PYDANTIC_V2 = True
except ImportError:
    # Fall back to pydantic v1
    from pydantic import validator, BaseModel, Field
    USING_PYDANTIC_V2 = False


class SearchQuery(BaseModel):
    """
    Schema for a structured search query to be executed across search engines.
    This is the core input model for search operations.
    """
    query: str = Field(..., description="The search query string")
    page: Optional[int] = Field(1, description="Page number for pagination")
    language: Optional[str] = Field(None, description="Language code (e.g. 'en')")
    region: Optional[str] = Field(None, description="Region code (e.g. 'us')")
    safe_search: Optional[bool] = Field(None, description="Whether to enable safe search")
    time_period: Optional[str] = Field(None, description="Time period for results (e.g. 'day', 'week', 'month', 'year')")
    sort_by: Optional[str] = Field(None, description="Sort criteria (e.g. 'relevance', 'date')")
    search_type: Optional[str] = Field("web", description="Type of search (e.g. 'web', 'images', 'news')")
    limit: Optional[int] = Field(10, description="Maximum number of results to return")

    def dict(self, *args, **kwargs):
        """Support for both pydantic v1 and v2 API"""
        if USING_PYDANTIC_V2:
            return super().model_dump(*args, **kwargs)
        else:
            return super().dict(*args, **kwargs)


class DomainSearchRequest(BaseModel):
    domain: str = Field(..., description="Company domain to search for")
    engines: Optional[List[str]] = Field(None, description="Search engines to use")
    pages: Optional[int] = Field(1, description="Number of pages to retrieve")
    ignore_duplicates: Optional[bool] = Field(True, description="Ignore duplicate results")
    use_proxy: Optional[bool] = Field(None, description="Whether to use proxy")
    
    @validator('domain')
    def validate_domain(cls, v):
        pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid domain name')
        return v


class FullSearchRequest(BaseModel):
    full_name: str = Field(..., description="Full name to search for")
    domain: str = Field(..., description="Company domain to search for")
    engines: Optional[List[str]] = Field(None, description="Search engines to use")
    pages: Optional[int] = Field(1, description="Number of pages to retrieve")
    ignore_duplicates: Optional[bool] = Field(True, description="Ignore duplicate results")
    use_proxy: Optional[bool] = Field(None, description="Whether to use proxy")
    
    @validator('domain')
    def validate_domain(cls, v):
        pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid domain name')
        return v


class CompanySearchRequest(BaseModel):
    company_name: str = Field(..., description="Company name to search for")
    engines: Optional[List[str]] = Field(None, description="Search engines to use")
    pages: Optional[int] = Field(1, description="Number of pages to retrieve")
    ignore_duplicates: Optional[bool] = Field(True, description="Ignore duplicate results")
    use_proxy: Optional[bool] = Field(None, description="Whether to use proxy")


class SearchResult(BaseModel):
    title: str = Field("", description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    snippet: str = Field("", description="Description or text snippet of the search result")
    
    # Alias for compatibility with different naming conventions
    @property
    def description(self) -> str:
        return self.snippet


class EngineResults(BaseModel):
    engine: str = Field(..., description="Name of the search engine")
    results: List[SearchResult] = Field(..., description="List of search results")
    total_results: int = Field(..., description="Total number of results found")


class SearchResponse(BaseModel):
    query: str = Field(..., description="The search query used")
    results_by_engine: List[EngineResults] = Field(..., description="Results grouped by search engine")
    combined_results: List[SearchResult] = Field(..., description="Combined unique results from all engines")
    total_results: int = Field(..., description="Total number of unique results")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata about the search") 