import time
import logging
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# simple in-process token bucket — good enough for a single instance
# for multi-instance deployments this should move to Redis (see Part 2 design doc)
RATE_LIMIT_REQUESTS = 30   # requests allowed per window
RATE_LIMIT_WINDOW = 60     # window in seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_window: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _get_client_ip(self, request: Request) -> str:
        # honour X-Forwarded-For if behind a proxy / load balancer
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        # skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        ip = self._get_client_ip(request)
        now = time.time()

        with self._lock:
            # drop timestamps outside the current window
            window_start = now - self.window_seconds
            self._buckets[ip] = [t for t in self._buckets[ip] if t > window_start]

            if len(self._buckets[ip]) >= self.requests_per_window:
                oldest = self._buckets[ip][0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                logger.warning("Rate limit hit for IP %s", ip)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down.", "code": "rate_limit_exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )

            self._buckets[ip].append(now)

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "%s %s -> %d (%dms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
