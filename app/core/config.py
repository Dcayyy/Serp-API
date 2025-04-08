from typing import List
import os
import sys

# Check pydantic version and import appropriate modules
try:
    # For pydantic 2.x
    from pydantic_settings import BaseSettings as Settings
    USING_PYDANTIC_V2 = True
except ImportError:
    # For pydantic 1.x
    from pydantic import BaseSettings as Settings
    USING_PYDANTIC_V2 = False

class Settings(Settings):
    PROJECT_NAME: str = "Search Engines Scraper API"
    API_V1_STR: str = "/api/v1"
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    
    # Search engines settings
    DEFAULT_SEARCH_ENGINES: List[str] = ["google", "bing", "yahoo", "duckduckgo"]
    MAX_SEARCH_PAGES: int = 1
    SEARCH_RESULTS_LIMIT: int = 10
    
    # Output settings
    OUTPUT_DIR: str = "search_results"
    
    # Scaling/distributed settings
    INSTANCE_ID: str = os.environ.get("INSTANCE_ID", "default")
    
    # Rate limiting to avoid detection
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Proxy settings (can be overridden by environment variables)
    USE_PROXY: bool = False
    PROXY_URL: str = ""
    
    # Timeout settings
    SEARCH_TIMEOUT: int = 30  # seconds
    
    # Concurrent execution settings
    USE_CONCURRENT_SEARCH: bool = True
    MAX_CONCURRENT_SEARCHES: int = 5

    # Rate limiting bypass settings
    USE_USER_AGENT_ROTATION: bool = True  # Enable user agent rotation
    USE_RANDOM_DELAYS: bool = True        # Enable random delays between requests
    MIN_REQUEST_DELAY: float = 0.5        # Minimum delay in seconds
    MAX_REQUEST_DELAY: float = 2.0        # Maximum delay in seconds

    # Configure to read from .env file
    if USING_PYDANTIC_V2:
        # Pydantic v2 config
        model_config = {
            "env_file": ".env",
            "case_sensitive": True
        }
    else:
        # Pydantic v1 config
        class Config:
            env_file = ".env"
            case_sensitive = True


settings = Settings() 