from setuptools import setup, find_packages

setup(
    name="search-engines-api",
    version="1.0.0",
    description="API for Search Engines Scraper",
    author="",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.103.1",
        "uvicorn>=0.23.0",
        "starlette>=0.27.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.25.0",
        "typing-extensions>=4.7.0",
        "search-engines @ git+https://github.com/tasos-py/Search-Engines-Scraper.git",
    ],
    python_requires=">=3.7",
)
