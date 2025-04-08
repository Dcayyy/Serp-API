from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os

from app.api.v1.api import api_router
from app.core.config import settings
from app.middleware import RateLimiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create output directory if it doesn't exist
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Search Engines Scraper API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiter middleware
app.add_middleware(
    RateLimiter,
    requests_limit=settings.RATE_LIMIT_REQUESTS,
    time_period=settings.RATE_LIMIT_PERIOD,
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["status"])
async def health_check():
    """Root endpoint for health checks."""
    return {"status": "ok", "message": "Search Engines Scraper API is running"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 