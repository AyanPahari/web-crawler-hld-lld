import re
from typing import Optional

from bs4 import BeautifulSoup


def _get_meta(soup: BeautifulSoup, name: str = None, prop: str = None) -> Optional[str]:
    """Pull content from a <meta> tag by name or property attribute."""
    tag = None
    if name:
        tag = soup.find("meta", attrs={"name": name})
    if not tag and prop:
        tag = soup.find("meta", attrs={"property": prop})
    if tag:
        return (tag.get("content") or "").strip() or None
    return None


def _clean_text(raw: str) -> str:
    """Collapse whitespace and strip control characters from extracted text."""
    text = re.sub(r"[\r\n\t]+", " ", raw)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def parse_html(html: str, url: str = "") -> dict:
    """
    Parse raw HTML and return a flat dict of all extractable signals.
    The extractor layer then ranks / derives topics from this.
    """
    soup = BeautifulSoup(html, "lxml")

    # --- title ---
    title_tag = soup.find("title")
    title = _clean_text(title_tag.get_text()) if title_tag else None

    # --- standard meta ---
    description = _get_meta(soup, name="description")
    keywords = _get_meta(soup, name="keywords")
    author = _get_meta(soup, name="author")
    robots = _get_meta(soup, name="robots")
    language = soup.find("html").get("lang", None) if soup.find("html") else None

    # --- open graph ---
    og_title = _get_meta(soup, prop="og:title")
    og_description = _get_meta(soup, prop="og:description")
    og_image = _get_meta(soup, prop="og:image")
    og_type = _get_meta(soup, prop="og:type")

    # --- twitter card ---
    twitter_title = _get_meta(soup, name="twitter:title")
    twitter_description = _get_meta(soup, name="twitter:description")

    # --- canonical ---
    canonical_tag = soup.find("link", rel="canonical")
    canonical_url = canonical_tag.get("href") if canonical_tag else None

    # --- headings ---
    h1_tags = [_clean_text(h.get_text()) for h in soup.find_all("h1") if h.get_text(strip=True)]
    h2_tags = [_clean_text(h.get_text()) for h in soup.find_all("h2") if h.get_text(strip=True)]

    # --- body text: remove scripts, styles, nav, footer first ---
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    body = soup.find("body")
    raw_body_text = body.get_text(separator=" ") if body else soup.get_text(separator=" ")
    body_text = _clean_text(raw_body_text)

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "author": author,
        "robots": robots,
        "language": language,
        "og_title": og_title,
        "og_description": og_description,
        "og_image": og_image,
        "og_type": og_type,
        "twitter_title": twitter_title,
        "twitter_description": twitter_description,
        "canonical_url": canonical_url,
        "h1_tags": h1_tags,
        "h2_tags": h2_tags,
        "body_text": body_text,
    }
