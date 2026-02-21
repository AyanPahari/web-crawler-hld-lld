import hashlib
import json
import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour default

# module-level client; None if Redis is unavailable (cache degrades gracefully)
_client: Optional[redis.Redis] = None


def get_client() -> Optional[redis.Redis]:
    global _client
    if _client is None:
        try:
            _client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            _client.ping()
        except Exception as exc:
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            _client = None
    return _client


def _cache_key(url: str) -> str:
    # use a short hash so keys stay small regardless of URL length
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"crawl:{digest}"


def get_cached(url: str) -> Optional[dict]:
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(url))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Cache read error: %s", exc)
        return None


def set_cached(url: str, data: dict, ttl: int = CACHE_TTL) -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.setex(_cache_key(url), ttl, json.dumps(data))
    except Exception as exc:
        logger.warning("Cache write error: %s", exc)


def is_cache_healthy() -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False
