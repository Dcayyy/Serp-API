# Search Engines API

A FastAPI application that provides a RESTful API for the [Search-Engines-Scraper](https://github.com/tasos-py/Search-Engines-Scraper) library.

## Features

- Search across multiple search engines (Google, Bing, Yahoo, DuckDuckGo)
- Multiple search modes (by company name, domain, full name, or custom query)
- RESTful API with Swagger documentation
- Rate limiting to avoid detection
- Scalable architecture

## Installation

### Using pip

```bash
# Install from GitHub
pip install git+https://github.com/your-username/Search-Engines-API.git
```

### Manual installation

```bash
# Clone the repository
git clone https://github.com/your-username/Search-Engines-API.git
cd Search-Engines-API

# Install the package
pip install -e .
```

## Usage

```bash
# Run the API server
python run.py
```

Then navigate to http://localhost:8000/docs to see the API documentation.

## API Endpoints

- `/api/v1/search/simple-search` - Search with a custom query
- `/api/v1/search/by-company-name` - Search for company information
- `/api/v1/search/by-domain` - Search by domain name
- `/api/v1/search/full-search` - Search for a person at a specific domain

## License

This project is licensed under the MIT License.
