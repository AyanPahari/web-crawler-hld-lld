# Web Metadata Crawler

A Python service that accepts any URL and returns structured page metadata — title, description, Open Graph tags, headings, body text, page type classification, and a ranked list of relevant topics extracted via TF-IDF.

## Live Demo (GCP Cloud Run)

**Base URL:** `https://web-crawler-1026938138024.us-central1.run.app`

**Interactive API docs:** [https://web-crawler-1026938138024.us-central1.run.app/docs](https://web-crawler-1026938138024.us-central1.run.app/docs)

```bash
# Health check
curl https://web-crawler-1026938138024.us-central1.run.app/health

# Crawl a URL
curl -X POST https://web-crawler-1026938138024.us-central1.run.app/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "http://www.cnn.com/2013/06/10/politics/edward-snowden-profile/"}'
```

## Design Documentation

| Document | Link |
|---|---|
| Part 2 — Scale Design (HLD) | [docs/Part-2 Scale Design.docx](docs/Part-2%20Scale%20Design.docx) |
| Part 3 — POC Engineering Plan (LLD) | [docs/Part-3 POC Plan.docx](docs/Part-3%20POC%20Plan.docx) |
| Architecture Diagram (Excalidraw) | [Open in browser →](https://excalidraw.com/#json=v6Jy4g8yVOVdEitK9x7sU,MBxeKFSsqVEbREjbwArixQ) |

### Architecture Overview

[![Architecture Diagram](https://excalidraw.com/#json=v6Jy4g8yVOVdEitK9x7sU,MBxeKFSsqVEbREjbwArixQ)](https://excalidraw.com/#json=v6Jy4g8yVOVdEitK9x7sU,MBxeKFSsqVEbREjbwArixQ)

The diagram covers the full two-stage pipeline — URL ingestion, politeness controller, Fetch Workers (Stage 1 → S3), Parse Workers (Stage 2 → PostgreSQL), Elasticsearch, Kafka topics, Redis, and monitoring. [Click to open →](https://excalidraw.com/#json=v6Jy4g8yVOVdEitK9x7sU,MBxeKFSsqVEbREjbwArixQ)

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

## Demo — Assignment URLs

To run the crawler against the three test URLs (Amazon, REI, CNN):

```bash
python3 test_crawl.py
```

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
  "page_type": "news_article",
  "word_count": 954,
  "error": null
}
```

`page_type` is one of: `product`, `news_article`, `blog_post`, `homepage`, `other`.

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

29 unit tests covering API endpoints, page classifier, topic extractor, HTML parser, and core crawl flow.

## Project Structure

```
├── crawler/
│   ├── core.py         # crawl() entry point
│   ├── fetcher.py      # HTTP fetch + robots.txt check
│   ├── parser.py       # BeautifulSoup HTML parsing
│   ├── extractor.py    # TF-IDF topic extraction
│   ├── classifier.py   # page type classification
│   └── models.py       # CrawlResult dataclass
├── api/
│   ├── main.py         # FastAPI app
│   ├── routes.py       # /crawl and /health endpoints
│   ├── cache.py        # Redis cache-aside layer
│   ├── middleware.py   # Rate limiting
│   └── schemas.py      # Pydantic request/response models
├── docs/
│   ├── Part-2 Scale Design.docx   # HLD — scale architecture
│   ├── Part-3 POC Plan.docx       # LLD — POC engineering plan
│   └── diagrams/
│       ├── arch_diagram.excalidraw
│       └── README.md
├── tests/              # 29 unit tests
├── test_crawl.py       # smoke test against the 3 assignment URLs
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
