from functools import wraps
import logging
from typing import Any, Dict, List, Optional, Type, Union, Callable

import httpx
from googlesearch import search as google_search
from duckduckgo_search import DDGS
from yahoosearchpy import YahooSearch
from py_bing_search import PyBingWebSearch

from app.core.config import settings
from app.models.search import SearchQuery, SearchResult
from app.utils.user_agent import UserAgentManager
from app.utils.throttle import RequestThrottler

logger = logging.getLogger(__name__)

# Initialize throttler
throttler = RequestThrottler()

class UserAgentMixin:
    """
    Mixin to add user agent support to search engines.
    Allows engines to use a randomly selected user agent or a specific user agent.
    """
    def __init__(self, *args, **kwargs):
        self._user_agent_manager = UserAgentManager()
        self.user_agent = None
        super().__init__(*args, **kwargs)
    
    def set_user_agent(self, user_agent: Optional[str] = None):
        """
        Set the user agent for the engine.
        If user_agent is None, a random user agent will be selected.
        """
        if user_agent is None and settings.USE_USER_AGENT_ROTATION:
            self.user_agent = self._user_agent_manager.get_random_user_agent()
        else:
            self.user_agent = user_agent
        
        return self.user_agent


class CustomGoogle(UserAgentMixin):
    """
    Custom Google search engine implementation that supports user agent rotation.
    """
    def search(self, query: SearchQuery) -> List[SearchResult]:
        self.set_user_agent()
        
        # Apply throttling before making the request
        throttler.throttle("google")
        
        results = []
        for j in google_search(
            query.query,
            tld="com",
            lang=query.language or "en",
            num=query.limit or 10,
            stop=query.limit or 10,
            pause=4.0,
            user_agent=self.user_agent
        ):
            results.append(SearchResult(title="", url=j, snippet=""))
        
        return results


class CustomBing(UserAgentMixin):
    """
    Custom Bing search engine implementation that supports user agent rotation.
    """
    def search(self, query: SearchQuery) -> List[SearchResult]:
        self.set_user_agent()
        
        # Apply throttling before making the request
        throttler.throttle("bing")
        
        api_key = settings.BING_API_KEY
        if not api_key:
            raise ValueError("Bing API key not configured")
        
        search_term = query.query
        limit = query.limit or 10
        
        bing_web = PyBingWebSearch(api_key, search_term, web_only=False)
        results = []
        
        # PyBingWebSearch doesn't have a direct user-agent setter, so we monkey patch it
        if hasattr(bing_web, "_search") and hasattr(bing_web._search, "session"):
            bing_web._search.session.headers["User-Agent"] = self.user_agent
        
        response = bing_web.search(limit=limit, format='json')
        
        for item in response:
            results.append(
                SearchResult(
                    title=item.title,
                    url=item.url,
                    snippet=item.description,
                )
            )
        
        return results


class CustomYahoo(UserAgentMixin):
    """
    Custom Yahoo search engine implementation that supports user agent rotation.
    """
    def search(self, query: SearchQuery) -> List[SearchResult]:
        self.set_user_agent()
        
        # Apply throttling before making the request
        throttler.throttle("yahoo")
        
        yahoo = YahooSearch(headers={"User-Agent": self.user_agent})
        raw_results = yahoo.search(query.query, limit=query.limit or 10)
        
        results = []
        for result in raw_results:
            results.append(
                SearchResult(
                    title=result.get("title", ""),
                    url=result.get("link", ""),
                    snippet=result.get("snippet", ""),
                )
            )
        
        return results


class CustomDuckduckgo(UserAgentMixin):
    """
    Custom DuckDuckGo search engine implementation that supports user agent rotation.
    """
    def search(self, query: SearchQuery) -> List[SearchResult]:
        self.set_user_agent()
        
        # Apply throttling before making the request
        throttler.throttle("duckduckgo")
        
        ddgs = DDGS()
        if self.user_agent:
            # Set user agent on the DDGS instance
            ddgs.headers["User-Agent"] = self.user_agent
        
        keywords = query.query
        region = query.region or "wt-wt"
        safesearch = "off"
        timelimit = None
        max_results = query.limit or 10
        
        results = []
        for r in ddgs.text(
            keywords, region=region, safesearch=safesearch, timelimit=timelimit, max_results=max_results
        ):
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                )
            )
        
        return results


# Map engine names to their custom implementation classes
CUSTOM_ENGINE_MAPPING: Dict[str, Type[Any]] = {
    "google": CustomGoogle,
    "bing": CustomBing,
    "yahoo": CustomYahoo,
    "duckduckgo": CustomDuckduckgo,
} 