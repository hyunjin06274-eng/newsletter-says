"""Phase 2.7: Group similar articles by topic — aggressive deduplication."""

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.45  # Lowered for more aggressive grouping


def normalize_text(text: str) -> str:
    """Normalize text for comparison — remove noise."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s가-힣]', '', text)  # Keep letters, numbers, Korean, spaces
    text = re.sub(r'\s+', ' ', text)
    return text


def text_similarity(a: str, b: str) -> float:
    """Calculate text similarity — compare both original and Korean titles."""
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0

    # Quick check: if one contains the other
    if a_norm in b_norm or b_norm in a_norm:
        return 0.9

    # Extract key nouns (3+ char words)
    a_words = set(w for w in a_norm.split() if len(w) >= 3)
    b_words = set(w for w in b_norm.split() if len(w) >= 3)
    if a_words and b_words:
        overlap = len(a_words & b_words)
        total = min(len(a_words), len(b_words))
        if total > 0 and overlap / total >= 0.6:
            return 0.7

    return SequenceMatcher(None, a_norm, b_norm).ratio()


def articles_similar(a: Article, b: Article) -> bool:
    """Check if two articles are about the same topic."""
    # Compare original titles
    sim1 = text_similarity(a.get("title", ""), b.get("title", ""))
    if sim1 >= SIMILARITY_THRESHOLD:
        return True

    # Compare Korean titles
    sim2 = text_similarity(a.get("title_kr", ""), b.get("title_kr", ""))
    if sim2 >= SIMILARITY_THRESHOLD:
        return True

    # Compare URLs (same article from different aggregators)
    url_a = a.get("url", "").split("?")[0].rstrip("/")
    url_b = b.get("url", "").split("?")[0].rstrip("/")
    if url_a and url_b and url_a == url_b:
        return True

    return False


def group_by_similarity(articles: list[Article]) -> list[Article]:
    """Group similar articles, keeping the highest-scored as representative."""
    if not articles:
        return []

    used = set()
    groups: list[Article] = []

    sorted_articles = sorted(articles, key=lambda a: a.get("score", 0), reverse=True)

    for i, article in enumerate(sorted_articles):
        if i in used:
            continue

        group_id = f"g{len(groups)}"
        article["group_id"] = group_id
        related_sources = []

        for j, other in enumerate(sorted_articles):
            if j <= i or j in used:
                continue

            if articles_similar(article, other):
                used.add(j)
                related_sources.append({
                    "title": other.get("title_kr", other.get("title", "")),
                    "url": other.get("url", ""),
                    "source": other.get("source", ""),
                })

        if related_sources:
            article["related_sources"] = related_sources
            logger.debug(
                f"Grouped '{article.get('title_kr', '')[:40]}' with {len(related_sources)} related"
            )

        groups.append(article)
        used.add(i)

    return groups


async def group_articles(state: NewsletterState) -> dict:
    """Group similar articles per country."""
    enriched = state.get("enriched_articles", {})
    grouped: dict[str, list[Article]] = {}

    for country, articles in enriched.items():
        before = len(articles)
        grouped_articles = group_by_similarity(articles)
        grouped[country] = grouped_articles
        removed = before - len(grouped_articles)
        logger.info(f"[{country}] Grouped: {before} -> {len(grouped_articles)} (-{removed} dupes)")
        print(f"[{country}] Grouped: {before} -> {len(grouped_articles)} (-{removed} dupes)", flush=True)

    return {
        "grouped_articles": grouped,
        "current_phase": "writing",
        "phase_status": {**state.get("phase_status", {}), "grouping": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "grouping", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in grouped.items()}}
        ],
    }
