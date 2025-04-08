import time
from typing import Dict, Tuple, List, Callable
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter(BaseHTTPMiddleware):
    """
    Middleware to implement rate limiting for search requests.
    
    This helps prevent detection and blocking by search engines by
    ensuring we don't send too many requests in a short period.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests_limit: int = settings.RATE_LIMIT_REQUESTS,
        time_period: int = settings.RATE_LIMIT_PERIOD,
    ):
        """
        Initialize the rate limiter middleware.
        
        Args:
            app: The ASGI application
            requests_limit: Maximum number of requests allowed in the time period
            time_period: Time period in seconds for rate limiting
        """
        super().__init__(app)
        self.requests_limit = requests_limit
        self.time_period = time_period
        self.request_timestamps: Dict[str, List[float]] = defaultdict(list)
        
        # Log configuration
        logger.info(
            f"Rate limiter configured: {requests_limit} requests per {time_period}s"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and apply rate limiting if needed.
        
        This method is called for each request and checks whether
        it should be rate limited based on the endpoint path.
        
        Args:
            request: The incoming request
            call_next: The next middleware or endpoint handler
            
        Returns:
            The response from the next handler
        """
        # Only rate limit search endpoints
        if "/search/" in request.url.path and request.method == "POST":
            path = request.url.path
            client_ip = request.client.host if request.client else "unknown"
            engine_key = f"{client_ip}:{path}"
            
            # Clear old timestamps
            current_time = time.time()
            cutoff_time = current_time - self.time_period
            
            # Remove timestamps older than the time period
            self.request_timestamps[engine_key] = [
                ts for ts in self.request_timestamps[engine_key] if ts > cutoff_time
            ]
            
            # Check if rate limit is exceeded
            if len(self.request_timestamps[engine_key]) >= self.requests_limit:
                oldest_timestamp = min(self.request_timestamps[engine_key])
                wait_time = self.time_period - (current_time - oldest_timestamp)
                
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit exceeded for {engine_key}. "
                        f"Waiting {wait_time:.2f}s before processing request."
                    )
                    
                    # Wait until we can process the request
                    await asyncio.sleep(wait_time)
                    
                    # Update timestamps after waiting
                    self.request_timestamps[engine_key] = [
                        ts for ts in self.request_timestamps[engine_key] if ts > (time.time() - self.time_period)
                    ]
            
            # Record this request timestamp
            self.request_timestamps[engine_key].append(time.time())
        
        # Process the request
        response = await call_next(request)
        return response 