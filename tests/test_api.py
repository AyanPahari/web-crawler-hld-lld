import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from crawler.models import CrawlResult

client = TestClient(app)

# a realistic CrawlResult to reuse across tests
MOCK_RESULT = CrawlResult(
    url="https://example.com/article",
    final_url="https://example.com/article",
    status_code=200,
    title="Example Article Title",
    description="An example article about web crawling.",
    og_type="article",
    language="en",
    h1_tags=["Example Article Title"],
    h2_tags=["Section 1", "Section 2"],
    body_text="This is the body text of the article about web crawling.",
    topics=["crawling", "web", "article", "example"],
    word_count=12,
)


# --- /health ---

def test_health_returns_ok():
    with patch("api.routes.is_cache_healthy", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["cache"] == "connected"


def test_health_when_cache_down():
    with patch("api.routes.is_cache_healthy", return_value=False):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["cache"] == "unavailable"


# --- /crawl ---

def test_crawl_success():
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.set_cached"), \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=MOCK_RESULT):
        response = client.post("/crawl", json={"url": "https://example.com/article"})

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Example Article Title"
    assert "crawling" in data["topics"]
    assert data["cached"] is False


def test_crawl_returns_cached_result():
    cached_data = MOCK_RESULT.to_dict()
    with patch("api.routes.get_cached", return_value=cached_data):
        response = client.post("/crawl", json={"url": "https://example.com/article"})

    assert response.status_code == 200
    assert response.json()["cached"] is True


def test_crawl_invalid_url_rejected():
    response = client.post("/crawl", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_crawl_missing_url_rejected():
    response = client.post("/crawl", json={})
    assert response.status_code == 422


def test_crawl_network_failure_returns_502():
    failed_result = CrawlResult(
        url="https://dead.example.com",
        final_url="https://dead.example.com",
        status_code=0,
        error="Connection timeout",
    )
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=failed_result):
        response = client.post("/crawl", json={"url": "https://dead.example.com"})

    assert response.status_code == 502
    assert "Failed to reach URL" in response.json()["detail"]


def test_crawl_robots_block_returns_result_with_error():
    # robots.txt blocks should return a result, not a 502 (status_code is 403, not 0)
    blocked_result = CrawlResult(
        url="https://blocked.example.com/page",
        final_url="https://blocked.example.com/page",
        status_code=403,
        error="robots.txt disallows crawling https://blocked.example.com/page",
    )
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.set_cached"), \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=blocked_result):
        response = client.post("/crawl", json={"url": "https://blocked.example.com/page"})

    assert response.status_code == 200
    data = response.json()
    assert data["status_code"] == 403
    assert "robots" in data["error"].lower()


def test_crawl_respect_robots_false_passes_through():
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.set_cached"), \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=MOCK_RESULT) as mock_crawl:
        client.post("/crawl", json={"url": "https://example.com/article", "respect_robots": False})

    mock_crawl.assert_called_once_with("https://example.com/article", respect_robots=False)


def test_successful_crawl_is_cached():
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.set_cached") as mock_set, \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=MOCK_RESULT):
        client.post("/crawl", json={"url": "https://example.com/article"})

    mock_set.assert_called_once()


def test_failed_crawl_is_not_cached():
    failed_result = CrawlResult(
        url="https://example.com/bad",
        final_url="https://example.com/bad",
        status_code=500,
        error="Server error",
    )
    with patch("api.routes.get_cached", return_value=None), \
         patch("api.routes.set_cached") as mock_set, \
         patch("api.routes.crawl", new_callable=AsyncMock, return_value=failed_result):
        client.post("/crawl", json={"url": "https://example.com/bad"})

    mock_set.assert_not_called()
