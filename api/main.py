import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .middleware import RateLimitMiddleware, RequestLoggingMiddleware
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Web Metadata Crawler",
    description=(
        "Given any URL, returns page metadata (title, description, open graph tags, "
        "headings, body text) and a ranked list of relevant topics extracted via TF-IDF."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# middleware stack — outermost runs first on request, last on response
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred.", "code": "internal_error"},
    )


app.include_router(router)
