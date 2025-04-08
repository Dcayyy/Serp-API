from search_engines import Google, Bing, Yahoo, Duckduckgo
import logging

logger = logging.getLogger(__name__)

class UserAgentMixin:
    """
    Mixin to add user agent support to search engine classes.
    This ensures that all our custom engine classes have consistent user agent support.
    """
    
    def set_user_agent(self, user_agent):
        """
        Set the user agent for the engine.
        
        Args:
            user_agent: User agent string
        """
        self.user_agent = user_agent
        
        # Ensure we have headers
        if not hasattr(self, 'headers'):
            self.headers = {}
        
        # Set the user agent in headers
        self.headers['User-Agent'] = user_agent
        
        # Also set it as USER_AGENT attribute for engines that might use that
        self.USER_AGENT = user_agent
    
    def _request(self, method, url, **kwargs):
        """
        Override the request method to ensure our user agent is used.
        This will be called by the search method of the engine.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments for the request
            
        Returns:
            Response from the request
        """
        # Ensure headers exist
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        # Set our user agent in the headers
        if hasattr(self, 'user_agent'):
            kwargs['headers']['User-Agent'] = self.user_agent
        
        # Call the original _request method from the parent class
        original_request = super()._request
        return original_request(method, url, **kwargs)


class CustomGoogle(UserAgentMixin, Google):
    """Custom Google search engine with guaranteed user agent support."""
    pass


class CustomBing(UserAgentMixin, Bing):
    """Custom Bing search engine with guaranteed user agent support."""
    pass


class CustomYahoo(UserAgentMixin, Yahoo):
    """Custom Yahoo search engine with guaranteed user agent support."""
    pass


class CustomDuckduckgo(UserAgentMixin, Duckduckgo):
    """Custom DuckDuckGo search engine with guaranteed user agent support."""
    pass


# Updated engine mapping for the factory
CUSTOM_ENGINE_MAPPING = {
    "google": CustomGoogle,
    "bing": CustomBing,
    "yahoo": CustomYahoo,
    "duckduckgo": CustomDuckduckgo
} 