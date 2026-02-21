import pytest
from crawler.parser import parse_html


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Best Camping Tents for 2024</title>
    <meta name="description" content="A guide to the top camping tents for outdoor enthusiasts.">
    <meta name="keywords" content="camping, tents, outdoor, hiking">
    <meta name="author" content="Jane Doe">
    <meta property="og:title" content="Top Camping Tents">
    <meta property="og:description" content="Expert picks for campers.">
    <meta property="og:image" content="https://example.com/tent.jpg">
    <meta property="og:type" content="article">
    <meta name="twitter:title" content="Best Tents 2024">
    <meta name="twitter:description" content="Our top picks for the season.">
    <link rel="canonical" href="https://example.com/camping-tents">
</head>
<body>
    <h1>Best Camping Tents</h1>
    <h2>Budget Picks</h2>
    <h2>Premium Picks</h2>
    <p>Looking for a great camping tent? Here's our curated list.</p>
    <script>alert("should be removed");</script>
    <nav>Navigation links here</nav>
    <footer>Footer content here</footer>
</body>
</html>
"""


def test_title_extracted():
    result = parse_html(SAMPLE_HTML)
    assert result["title"] == "Best Camping Tents for 2024"


def test_meta_description():
    result = parse_html(SAMPLE_HTML)
    assert "camping tents" in result["description"].lower()


def test_meta_keywords():
    result = parse_html(SAMPLE_HTML)
    assert "camping" in result["keywords"]


def test_og_tags():
    result = parse_html(SAMPLE_HTML)
    assert result["og_title"] == "Top Camping Tents"
    assert result["og_type"] == "article"
    assert result["og_image"] == "https://example.com/tent.jpg"


def test_twitter_tags():
    result = parse_html(SAMPLE_HTML)
    assert result["twitter_title"] == "Best Tents 2024"


def test_canonical_url():
    result = parse_html(SAMPLE_HTML)
    assert result["canonical_url"] == "https://example.com/camping-tents"


def test_headings():
    result = parse_html(SAMPLE_HTML)
    assert "Best Camping Tents" in result["h1_tags"]
    assert "Budget Picks" in result["h2_tags"]
    assert "Premium Picks" in result["h2_tags"]


def test_language():
    result = parse_html(SAMPLE_HTML)
    assert result["language"] == "en"


def test_author():
    result = parse_html(SAMPLE_HTML)
    assert result["author"] == "Jane Doe"


def test_script_and_nav_stripped_from_body():
    result = parse_html(SAMPLE_HTML)
    body = result["body_text"]
    assert "alert" not in body
    assert "Navigation links" not in body
    assert "Footer content" not in body


def test_body_contains_content():
    result = parse_html(SAMPLE_HTML)
    assert "camping tent" in result["body_text"].lower()


def test_empty_html_does_not_crash():
    result = parse_html("")
    assert result["title"] is None
    assert result["h1_tags"] == []
