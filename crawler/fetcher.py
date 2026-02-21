import asyncio
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

# realistic browser UA — avoids most trivial bot blocks
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 15  # seconds
MAX_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB ceiling to avoid runaway pages


def _robots_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def is_crawl_allowed(url: str, user_agent: str = "*") -> bool:
    """Check robots.txt for the given URL. Returns True if crawling is allowed."""
    robots_url = _robots_url(url)
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # if robots.txt is unreachable, assume allowed
        return True


def _sync_fetch(url: str) -> tuple[str, int, str]:
    """Synchronous fetch using requests — runs inside a thread executor."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    content = response.text[:MAX_CONTENT_BYTES]
    return content, response.status_code, response.url


async def fetch_page(url: str, respect_robots: bool = True) -> tuple[str, int, str]:
    """
    Fetch the HTML content of a URL asynchronously.

    Uses requests in a thread executor to stay non-blocking inside the async
    event loop while relying on the standard synchronous DNS resolver.
    Returns (html_content, status_code, final_url).
    """
    if respect_robots and not is_crawl_allowed(url):
        raise PermissionError(f"robots.txt disallows crawling {url}")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch, url)
