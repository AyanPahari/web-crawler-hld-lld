import logging

from fastapi import APIRouter, HTTPException

from crawler.core import crawl
from .cache import get_cached, set_cached, is_cache_healthy
from .schemas import CrawlRequest, CrawlResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/crawl", response_model=CrawlResponse, summary="Crawl a URL and extract metadata")
async def crawl_url(request: CrawlRequest) -> CrawlResponse:
    """
    Accepts a URL and returns all extractable metadata plus a ranked list of topics.

    - Checks Redis cache first; returns cached result if available.
    - Respects robots.txt by default (`respect_robots: true`).
    - Set `respect_robots: false` to bypass the robots.txt check (useful for testing).
    """
    url = request.url

    # cache-aside: serve from Redis if we've crawled this URL recently
    cached = get_cached(url)
    if cached:
        logger.info("Cache hit for %s", url)
        return CrawlResponse(**cached, cached=True)

    result = await crawl(url, respect_robots=request.respect_robots)

    if result.error and result.status_code == 0:
        # complete network failure — don't cache, surface as HTTP 502
        raise HTTPException(status_code=502, detail=f"Failed to reach URL: {result.error}")

    response_data = result.to_dict()

    # only cache successful fetches — don't cache network errors or robots blocks
    if result.status_code == 200:
        set_cached(url, response_data)

    return CrawlResponse(**response_data, cached=False)


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    cache_status = "connected" if is_cache_healthy() else "unavailable"
    return HealthResponse(status="ok", cache=cache_status)
