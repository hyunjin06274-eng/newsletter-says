"""Phase 2.7: Group similar articles by topic."""

import logging
from datetime import datetime
from difflib import SequenceMatcher

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6


def title_similarity(a: str, b: str) -> float:
    """Calculate title similarity ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def group_by_similarity(articles: list[Article]) -> list[Article]:
    """Group similar articles, keeping the highest-scored as representative."""
    if not articles:
        return []

    used = set()
    groups: list[Article] = []

    # Sort by score descending so best articles are representatives
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

            sim = title_similarity(
                article.get("title", ""), other.get("title", "")
            )
            if sim >= SIMILARITY_THRESHOLD:
                used.add(j)
                related_sources.append({
                    "title": other.get("title", ""),
                    "url": other.get("url", ""),
                    "source": other.get("source", ""),
                })

        if related_sources:
            article["related_sources"] = related_sources

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
        logger.info(f"[{country}] Grouped: {before} -> {len(grouped_articles)} representative articles")

    return {
        "grouped_articles": grouped,
        "current_phase": "writing",
        "phase_status": {**state.get("phase_status", {}), "grouping": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "grouping", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in grouped.items()}}
        ],
    }
