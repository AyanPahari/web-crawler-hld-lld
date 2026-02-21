import logging

from .fetcher import fetch_page
from .parser import parse_html
from .extractor import extract_metadata
from .models import CrawlResult

logger = logging.getLogger(__name__)


async def crawl(url: str, respect_robots: bool = True) -> CrawlResult:
    """
    Top-level entry point. Fetches, parses, and extracts metadata from any URL.
    Returns a CrawlResult — never raises; errors are captured in result.error.
    """
    try:
        html, status_code, final_url = await fetch_page(url, respect_robots=respect_robots)
    except PermissionError as exc:
        logger.warning("Robots disallow: %s", url)
        return CrawlResult(url=url, final_url=url, status_code=403, error=str(exc))
    except Exception as exc:
        logger.error("Fetch failed for %s: %s", url, exc)
        return CrawlResult(url=url, final_url=url, status_code=0, error=str(exc))

    try:
        parsed = parse_html(html, url=final_url)
        result = extract_metadata(parsed, url=url, final_url=final_url, status_code=status_code)
    except Exception as exc:
        logger.error("Parse/extract failed for %s: %s", url, exc)
        return CrawlResult(url=url, final_url=final_url, status_code=status_code, error=str(exc))

    return result
