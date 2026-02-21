import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from crawler.core import crawl


MOCK_HTML = """
<html lang="en">
<head>
    <title>Edward Snowden Profile | CNN Politics</title>
    <meta name="description" content="Edward Snowden leaked NSA surveillance secrets.">
    <meta property="og:type" content="article">
    <meta name="author" content="CNN Staff">
</head>
<body>
    <h1>Man behind NSA leaks</h1>
    <p>Edward Snowden revealed details about government surveillance programs in 2013.</p>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_crawl_success():
    with patch("crawler.core.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (MOCK_HTML, 200, "https://cnn.com/story")
        result = await crawl("http://cnn.com/story")

    assert result.status_code == 200
    assert result.error is None
    assert "Snowden" in result.title or "NSA" in result.title
    assert len(result.topics) > 0


@pytest.mark.asyncio
async def test_crawl_robots_blocked():
    with patch("crawler.core.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = PermissionError("robots.txt disallows crawling http://blocked.com/")
        result = await crawl("http://blocked.com/")

    assert result.status_code == 403
    assert result.error is not None
    assert "robots" in result.error.lower()


@pytest.mark.asyncio
async def test_crawl_network_error():
    with patch("crawler.core.fetch_page", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = Exception("Connection timeout")
        result = await crawl("http://unreachable.example.com/")

    assert result.status_code == 0
    assert result.error == "Connection timeout"


@pytest.mark.asyncio
async def test_crawl_captures_final_url_after_redirect():
    with patch("crawler.core.fetch_page", new_callable=AsyncMock) as mock_fetch:
        # simulates http -> https redirect
        mock_fetch.return_value = (MOCK_HTML, 200, "https://cnn.com/story")
        result = await crawl("http://cnn.com/story")

    assert result.final_url == "https://cnn.com/story"
    assert result.url == "http://cnn.com/story"
