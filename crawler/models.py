from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CrawlResult:
    url: str
    final_url: str                      # may differ from input after redirects
    status_code: int

    # standard meta tags
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None

    # open graph / social tags
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None

    # twitter card
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

    # page basics
    canonical_url: Optional[str] = None
    language: Optional[str] = None
    author: Optional[str] = None
    robots: Optional[str] = None

    # extracted content
    h1_tags: list[str] = field(default_factory=list)
    h2_tags: list[str] = field(default_factory=list)
    body_text: Optional[str] = None         # cleaned plaintext of the page body

    # derived
    topics: list[str] = field(default_factory=list)     # top keywords / topics ranked by TF-IDF
    page_type: str = "other"                            # product | news_article | blog_post | homepage | other
    word_count: int = 0

    # error info (populated only on failure)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}
