import pytest
from crawler.classifier import classify_page


# --- helpers ---
def make_parsed(og_type=None, title="", h1_tags=None, description=""):
    return {
        "og_type": og_type,
        "title": title,
        "h1_tags": h1_tags or [],
        "description": description,
    }


# --- the three assignment URLs (most important tests) ---

def test_amazon_toaster_classified_as_product():
    url = "https://www.amazon.com/Cuisinart-CPT-122-Compact-2-Slice-Toaster/dp/B009GQ034C/"
    parsed = make_parsed(title="Cuisinart 2-Slice Toaster, Compact, White, CPT-122: Home & Kitchen")
    assert classify_page(parsed, url) == "product"


def test_rei_blog_classified_as_blog_post():
    url = "https://www.rei.com/blog/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors"
    parsed = make_parsed(og_type="article", title="How to Introduce Your Indoorsy Friend to the Outdoors")
    assert classify_page(parsed, url) == "blog_post"


def test_cnn_snowden_classified_as_news_article():
    url = "https://edition.cnn.com/2013/06/10/politics/edward-snowden-profile/"
    parsed = make_parsed(og_type="article", title="Man behind NSA leaks says he did it to safeguard privacy")
    assert classify_page(parsed, url) == "news_article"


# --- og:type direct mapping ---

def test_og_type_product_returns_product():
    assert classify_page(make_parsed(og_type="product"), "https://example.com/anything") == "product"


def test_og_type_product_item_returns_product():
    assert classify_page(make_parsed(og_type="product.item"), "https://example.com/anything") == "product"


# --- product URL pattern signals ---

def test_dp_path_returns_product():
    assert classify_page(make_parsed(), "https://amazon.com/SomeName/dp/B001234/") == "product"


def test_product_path_returns_product():
    assert classify_page(make_parsed(), "https://shop.example.com/product/widget-pro") == "product"


def test_items_path_returns_product():
    assert classify_page(make_parsed(), "https://bestbuy.com/items/12345") == "product"


def test_buy_path_returns_product():
    assert classify_page(make_parsed(), "https://example.com/buy/headphones") == "product"


# --- homepage detection ---

def test_root_path_returns_homepage():
    assert classify_page(make_parsed(), "https://www.amazon.com/") == "homepage"


def test_bare_domain_returns_homepage():
    assert classify_page(make_parsed(), "https://www.amazon.com") == "homepage"


def test_index_html_returns_homepage():
    assert classify_page(make_parsed(), "https://example.com/index.html") == "homepage"


# --- news article signals ---

def test_politics_path_returns_news():
    assert classify_page(make_parsed(og_type="article"), "https://cnn.com/politics/some-story") == "news_article"


def test_world_path_returns_news():
    assert classify_page(make_parsed(og_type="article"), "https://bbc.com/world/article-123") == "news_article"


def test_date_based_url_returns_news():
    assert classify_page(make_parsed(og_type="article"), "https://nytimes.com/2024/03/15/tech/ai-story") == "news_article"


def test_news_path_without_og_type_returns_news():
    assert classify_page(make_parsed(), "https://example.com/news/some-headline") == "news_article"


def test_date_url_without_og_type_returns_news():
    assert classify_page(make_parsed(), "https://example.com/2022/11/01/some-event/") == "news_article"


# --- blog post signals ---

def test_blog_path_returns_blog_post():
    assert classify_page(make_parsed(og_type="article"), "https://example.com/blog/my-post") == "blog_post"


def test_how_to_path_returns_blog_post():
    assert classify_page(make_parsed(og_type="article"), "https://example.com/how-to/use-a-tent") == "blog_post"


def test_guide_path_returns_blog_post():
    assert classify_page(make_parsed(), "https://example.com/guide/beginners-guide") == "blog_post"


def test_camp_path_returns_blog_post():
    assert classify_page(make_parsed(og_type="article"), "https://rei.com/blog/camp/tips-for-camping") == "blog_post"


def test_og_article_no_url_signal_defaults_to_blog_post():
    # og:type=article with a generic URL — no news or blog signal — defaults to blog_post
    assert classify_page(make_parsed(og_type="article"), "https://example.com/some-page/") == "blog_post"


# --- content keyword fallback ---

def test_product_content_signals_return_product():
    parsed = make_parsed(title="buy now at best price free shipping add to cart")
    assert classify_page(parsed, "https://example.com/gadget-x") == "product"


def test_news_content_signals_return_news():
    parsed = make_parsed(title="exclusive investigation leaked documents officials said")
    assert classify_page(parsed, "https://example.com/story-x") == "news_article"


def test_blog_content_signals_return_blog():
    parsed = make_parsed(description="in this guide we cover step by step tips for beginners")
    assert classify_page(parsed, "https://example.com/random-page") == "blog_post"


# --- other / fallback ---

def test_no_signals_returns_other():
    parsed = make_parsed(title="Contact us", h1_tags=["Get in touch"])
    assert classify_page(parsed, "https://example.com/contact") == "other"


def test_empty_parsed_returns_other():
    assert classify_page({}, "https://example.com/zzz") == "other"
