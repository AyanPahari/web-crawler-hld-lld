import re
from urllib.parse import urlparse


# Page type labels used throughout the system
PAGE_TYPES = ("product", "news_article", "blog_post", "homepage", "other")

# --- signal tables ---

# og:type values that map unambiguously to a page type
_OG_TYPE_MAP: dict[str, str] = {
    "product":        "product",
    "product.item":   "product",
    "book":           "other",
    "music.song":     "other",
    "video.movie":    "other",
    "website":        None,    # ambiguous — fall through to URL signals
    "article":        None,    # ambiguous — news vs blog, decide by URL
}

# URL path fragments — ordered from most to least specific
_PRODUCT_URL_SIGNALS = [
    "/dp/",           # Amazon product pages
    "/product/", "/products/",
    "/item/", "/items/",
    "/pd/",           # Target / some e-commerce
    "/buy/",
    "/gp/product/",   # Amazon alternate path
]

_NEWS_URL_SIGNALS = [
    "/politics/", "/world/", "/us/", "/business/",
    "/health/", "/science/", "/sports/", "/entertainment/",
    "/tech/", "/technology/", "/national/", "/international/",
    "/news/", "/breaking/", "/latest/",
]

_BLOG_URL_SIGNALS = [
    "/blog/", "/blogs/",
    "/post/", "/posts/",
    "/how-to/", "/howto/",
    "/guide/", "/guides/",
    "/tips/", "/tutorial/",
    "/camp/",         # REI Co-op blog
    "/adventure/", "/outdoor/",
]

# date-based URL pattern — common in news (e.g. /2013/06/10/)
_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/")

# content keyword signals — used only when URL gives no signal
_PRODUCT_CONTENT = [
    "add to cart", "buy now", "in stock", "out of stock",
    "free shipping", "price", "rating", "stars out of",
]
_NEWS_CONTENT = [
    "breaking news", "exclusive", "investigation", "leaked",
    "officials said", "according to", "press release",
]
_BLOG_CONTENT = [
    "how to", "step by step", "in this guide", "tips for",
    "here's why", "let's look at",
]


def classify_page(parsed: dict, url: str) -> str:
    """
    Classify a crawled page into one of five types:
      product | news_article | blog_post | homepage | other

    Priority order:
      1. og:type (unambiguous values)
      2. URL path patterns (structural, reliable)
      3. Homepage detection (trivially short path)
      4. og:type = "article" disambiguated by URL
      5. Content keyword scoring (weakest signal, last resort)
    """
    url_lower = url.lower()
    og_type = (parsed.get("og_type") or "").lower().strip()
    title = (parsed.get("title") or "").lower()
    h1_text = " ".join(parsed.get("h1_tags", [])).lower()
    description = (parsed.get("description") or "").lower()
    content = f"{title} {h1_text} {description}"

    # 1. og:type with an unambiguous mapping
    if og_type in _OG_TYPE_MAP and _OG_TYPE_MAP[og_type] is not None:
        return _OG_TYPE_MAP[og_type]

    # 2. URL path — product patterns are very reliable
    for signal in _PRODUCT_URL_SIGNALS:
        if signal in url_lower:
            return "product"

    # 3. Homepage — path is "/" or effectively empty
    path = urlparse(url).path.rstrip("/")
    if not path or path in ("/index.html", "/index.php", "/home"):
        return "homepage"

    # 4. og:type = "article" — reliable that it's written content, but need URL
    #    to tell whether it's news or a blog post
    if og_type == "article":
        for signal in _NEWS_URL_SIGNALS:
            if signal in url_lower:
                return "news_article"
        # date-based URL is a strong news signal (e.g. cnn.com/2013/06/10/...)
        if _DATE_URL_RE.search(url_lower):
            return "news_article"
        for signal in _BLOG_URL_SIGNALS:
            if signal in url_lower:
                return "blog_post"
        # og:type = "article" with no further URL signal → treat as blog post
        return "blog_post"

    # 5. URL path signals without og:type help
    for signal in _NEWS_URL_SIGNALS:
        if signal in url_lower:
            return "news_article"
    if _DATE_URL_RE.search(url_lower):
        return "news_article"
    for signal in _BLOG_URL_SIGNALS:
        if signal in url_lower:
            return "blog_post"

    # 6. Content keyword scoring — last resort before giving up
    product_score = sum(1 for s in _PRODUCT_CONTENT if s in content)
    news_score = sum(1 for s in _NEWS_CONTENT if s in content)
    blog_score = sum(1 for s in _BLOG_CONTENT if s in content)

    top = max(product_score, news_score, blog_score)
    if top > 0:
        if product_score == top:
            return "product"
        if news_score == top:
            return "news_article"
        if blog_score == top:
            return "blog_post"

    return "other"
