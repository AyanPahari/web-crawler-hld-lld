# Web Metadata Crawler

A Python service that accepts any URL and returns structured page metadata — title, description, Open Graph tags, headings, body text, and a ranked list of relevant topics extracted via TF-IDF.

## Quick Start (Docker)

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

## Quick Start (local)

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

> Without Redis running, caching is automatically disabled and the service continues to work normally.

## API

### `POST /crawl`

Crawl a URL and return its metadata and topics.

**Request**
```json
{
  "url": "https://www.cnn.com/2013/06/10/politics/edward-snowden-profile/",
  "respect_robots": true
}
```

**Response**
```json
{
  "url": "https://www.cnn.com/...",
  "final_url": "https://edition.cnn.com/...",
  "status_code": 200,
  "cached": false,
  "title": "Man behind NSA leaks says he did it to safeguard privacy, liberty",
  "description": "Edward Snowden might never live in the U.S. as a free man again...",
  "author": "Barbara Starr,Holly Yan",
  "og_type": "article",
  "og_image": "https://media.cnn.com/...",
  "canonical_url": "https://www.cnn.com/...",
  "language": "en",
  "h1_tags": ["Man behind NSA leaks..."],
  "h2_tags": ["Download the CNN app"],
  "topics": ["nsa", "snowden", "privacy", "leaks", "surveillance", ...],
  "word_count": 954,
  "error": null
}
```

Set `respect_robots: false` to bypass the robots.txt check (for testing/demo purposes only).

### `GET /health`

```json
{ "status": "ok", "cache": "connected" }
```

`cache` is `"unavailable"` when Redis is not reachable — the service continues to function, just without caching.

## Rate Limiting

30 requests per 60 seconds per IP. Exceeding this returns HTTP 429 with a `Retry-After` header.

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
├── crawler/
│   ├── core.py         # crawl() entry point
│   ├── fetcher.py      # HTTP fetch + robots.txt check
│   ├── parser.py       # BeautifulSoup HTML parsing
│   ├── extractor.py    # TF-IDF topic extraction
│   └── models.py       # CrawlResult dataclass
├── api/
│   ├── main.py         # FastAPI app
│   ├── routes.py       # /crawl and /health endpoints
│   ├── cache.py        # Redis cache-aside layer
│   ├── middleware.py   # Rate limiting + request logging
│   └── schemas.py      # Pydantic request/response models
├── tests/              # 35 unit tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
