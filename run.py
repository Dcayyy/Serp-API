#!/usr/bin/env python
import os
import sys
import uvicorn
import logging

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("search_api")

def check_compatibility():
    """Check if the Python version is compatible with the application."""
    python_version = sys.version_info
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        logger.error(f"Python version {python_version.major}.{python_version.minor} is not supported. Please use Python 3.7+")
        return False
    
    # Special note for Python 3.13+ users
    if python_version.major == 3 and python_version.minor >= 13:
        logger.warning(
            f"Running on Python {python_version.major}.{python_version.minor}. "
            "This is a newer Python version and may have compatibility issues. "
            "If you encounter problems, consider using Python 3.10-3.12."
        )
    
    return True

def setup_directories():
    """Create necessary directories for the application."""
    # Create search results directory
    os.makedirs("search_results", exist_ok=True)
    logger.info("Created search_results directory")

def main():
    """Run the Search Engines Scraper API application."""
    print("Starting Search Engines Scraper API...")
    
    # Check compatibility
    if not check_compatibility():
        sys.exit(1)
    
    # Set up directories
    setup_directories()
    
    # Log Python version
    python_version = sys.version_info
    logger.info(f"Running on Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    try:
        # Run the application
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 