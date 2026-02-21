from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


class CrawlRequest(BaseModel):
    url: str
    respect_robots: bool = True  # set False only for testing/demo purposes

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CrawlResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    cached: bool = False

    # standard meta
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None

    # open graph
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None

    # twitter card
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

    # page signals
    canonical_url: Optional[str] = None
    language: Optional[str] = None
    author: Optional[str] = None
    robots: Optional[str] = None

    h1_tags: list[str] = []
    h2_tags: list[str] = []
    body_text: Optional[str] = None
    word_count: int = 0

    # derived
    topics: list[str] = []
    page_type: str = "other"    # product | news_article | blog_post | homepage | other

    # error info
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    cache: str  # "connected" or "unavailable"


class ErrorResponse(BaseModel):
    detail: str
    code: str
