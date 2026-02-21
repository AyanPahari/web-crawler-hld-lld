import re
import logging
from typing import Optional

import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import CrawlResult
from .parser import parse_html

logger = logging.getLogger(__name__)

# download once; no-op if already present
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

_STOP_WORDS = set(stopwords.words("english"))

# bare minimum additional noise words common on web pages
_EXTRA_NOISE = {
    "click", "please", "read", "more", "also", "like", "get", "use",
    "new", "one", "two", "first", "will", "may", "can", "make", "see",
    "know", "way", "time", "year", "day", "back", "come", "go", "take",
    "want", "need", "look", "give", "think", "good", "well", "right",
    "say", "said", "says", "us", "want", "re", "ve", "ll", "don",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove short/stop words."""
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and t not in _EXTRA_NOISE]


def _build_corpus(parsed: dict) -> str:
    """
    Build a weighted corpus for TF-IDF by repeating high-signal fields.
    Title and headings get more weight than body text.
    """
    parts = []

    # repeat title 5x — strongest signal
    if parsed.get("title"):
        parts.extend([parsed["title"]] * 5)

    # meta description is very intent-dense
    if parsed.get("description"):
        parts.extend([parsed["description"]] * 3)

    # og_title / og_description are usually accurate
    if parsed.get("og_title"):
        parts.extend([parsed["og_title"]] * 3)
    if parsed.get("og_description"):
        parts.extend([parsed["og_description"]] * 2)

    # headings
    for h in parsed.get("h1_tags", []):
        parts.extend([h] * 4)
    for h in parsed.get("h2_tags", []):
        parts.extend([h] * 2)

    # body contributes but with lower weight (just appended once)
    if parsed.get("body_text"):
        # cap body at 10k chars to keep TF-IDF fast
        parts.append(parsed["body_text"][:10000])

    return " ".join(parts)


def _extract_topics(corpus: str, top_n: int = 15) -> list[str]:
    """
    Run TF-IDF on the corpus and return the top_n scoring terms.
    Uses a single-document approach — scores are term frequencies weighted
    by inverse document frequency from the sklearn default corpus.
    """
    if not corpus.strip():
        return []

    tokens = _tokenize(corpus)
    if not tokens:
        return []

    # join back for vectorizer
    clean_corpus = " ".join(tokens)

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),        # single words + bigrams
            max_features=200,
            sublinear_tf=True,         # log(tf) dampens very high frequencies
        )
        tfidf_matrix = vectorizer.fit_transform([clean_corpus])
        scores = zip(vectorizer.get_feature_names_out(), tfidf_matrix.toarray()[0])
        ranked = sorted(scores, key=lambda x: x[1], reverse=True)
        return [term for term, score in ranked[:top_n] if score > 0]
    except Exception as exc:
        logger.warning("TF-IDF extraction failed: %s", exc)
        return []


def extract_metadata(parsed: dict, url: str, final_url: str, status_code: int) -> CrawlResult:
    """
    Combine parsed HTML signals into a CrawlResult with derived topic list.
    """
    corpus = _build_corpus(parsed)
    topics = _extract_topics(corpus)

    body_text = parsed.get("body_text", "")
    word_count = len(body_text.split()) if body_text else 0

    return CrawlResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        title=parsed.get("title"),
        description=parsed.get("description"),
        keywords=parsed.get("keywords"),
        og_title=parsed.get("og_title"),
        og_description=parsed.get("og_description"),
        og_image=parsed.get("og_image"),
        og_type=parsed.get("og_type"),
        twitter_title=parsed.get("twitter_title"),
        twitter_description=parsed.get("twitter_description"),
        canonical_url=parsed.get("canonical_url"),
        language=parsed.get("language"),
        author=parsed.get("author"),
        robots=parsed.get("robots"),
        h1_tags=parsed.get("h1_tags", []),
        h2_tags=parsed.get("h2_tags", []),
        body_text=body_text[:2000] if body_text else None,  # truncate for storage
        topics=topics,
        word_count=word_count,
    )
