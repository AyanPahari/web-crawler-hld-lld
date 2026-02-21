import pytest
from crawler.extractor import extract_metadata, _extract_topics, _build_corpus


SAMPLE_PARSED = {
    "title": "Cuisinart CPT-122 Compact 2-Slice Toaster Review",
    "description": "A detailed review of the Cuisinart compact toaster with bagel and defrost settings.",
    "keywords": "toaster, cuisinart, kitchen appliance",
    "og_title": "Cuisinart Toaster Review",
    "og_description": "Compact 2-slice toaster for small kitchens",
    "og_image": "https://example.com/toaster.jpg",
    "og_type": "product",
    "twitter_title": None,
    "twitter_description": None,
    "canonical_url": "https://example.com/toaster-review",
    "language": "en",
    "author": None,
    "robots": None,
    "h1_tags": ["Cuisinart CPT-122 Toaster"],
    "h2_tags": ["Features", "Bagel Setting", "Price and Value"],
    "body_text": (
        "The Cuisinart CPT-122 is a compact 2-slice toaster ideal for small kitchens. "
        "It features a bagel setting, defrost mode, and a reheat option. "
        "At its price point, it offers excellent value for kitchen appliances."
    ),
}


def test_extract_metadata_returns_crawl_result():
    result = extract_metadata(SAMPLE_PARSED, url="http://example.com", final_url="http://example.com", status_code=200)
    assert result.url == "http://example.com"
    assert result.status_code == 200


def test_title_and_description_passed_through():
    result = extract_metadata(SAMPLE_PARSED, url="http://example.com", final_url="http://example.com", status_code=200)
    assert "Cuisinart" in result.title
    assert result.description is not None


def test_topics_extracted():
    result = extract_metadata(SAMPLE_PARSED, url="http://example.com", final_url="http://example.com", status_code=200)
    assert len(result.topics) > 0
    # toaster or cuisinart should rank highly
    assert any(t in ("toaster", "cuisinart", "compact") for t in result.topics)


def test_word_count_calculated():
    result = extract_metadata(SAMPLE_PARSED, url="http://example.com", final_url="http://example.com", status_code=200)
    assert result.word_count > 0


def test_topics_from_empty_corpus():
    topics = _extract_topics("")
    assert topics == []


def test_build_corpus_weights_title():
    # title appears 5x in corpus — check it dominates
    corpus = _build_corpus(SAMPLE_PARSED)
    assert corpus.count("Cuisinart CPT-122 Compact 2-Slice Toaster Review") == 5


def test_h1_h2_in_result():
    result = extract_metadata(SAMPLE_PARSED, url="http://example.com", final_url="http://example.com", status_code=200)
    assert "Cuisinart CPT-122 Toaster" in result.h1_tags
    assert "Bagel Setting" in result.h2_tags


def test_body_text_truncated_in_result():
    long_body = "word " * 1000
    parsed = {**SAMPLE_PARSED, "body_text": long_body}
    result = extract_metadata(parsed, url="http://example.com", final_url="http://example.com", status_code=200)
    # body_text stored in result is capped at 2000 chars
    assert len(result.body_text) <= 2000
