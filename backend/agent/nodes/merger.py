"""Phase 1.5: Merge domain results and deduplicate."""

import logging
from datetime import datetime
from urllib.parse import urlparse

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

DOMAIN_PRIORITY = {"competitor": 0, "lubricant": 1, "industry": 2, "macro": 3}


def dedupe_articles(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles by URL, keeping highest priority domain."""
    seen_urls: dict[str, Article] = {}

    # Sort by domain priority (lower = higher priority)
    sorted_articles = sorted(
        articles,
        key=lambda a: DOMAIN_PRIORITY.get(a.get("collection_domain", "macro"), 9),
    )

    for article in sorted_articles:
        url = article.get("url", "")
        if not url:
            continue
        # Normalize URL
        parsed = urlparse(url)
        normalized = f"{parsed.netloc}{parsed.path}".rstrip("/").lower()

        if normalized not in seen_urls:
            seen_urls[normalized] = article

    return list(seen_urls.values())


async def merge_and_dedupe(state: NewsletterState) -> dict:
    """Merge domain results and remove duplicates per country."""
    raw_articles = state.get("raw_articles", {})
    merged: dict[str, list[Article]] = {}

    for country, articles in raw_articles.items():
        before = len(articles)
        deduped = dedupe_articles(articles)
        merged[country] = deduped
        logger.info(f"[{country}] Merged: {before} -> {len(deduped)} (removed {before - len(deduped)} dupes)")
        print(f"[{country}] Merged: {before} -> {len(deduped)} (removed {before - len(deduped)} dupes)", flush=True)

    return {
        "merged_articles": merged,
        "current_phase": "scoring",
        "phase_status": {**state.get("phase_status", {}), "merge": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "merge", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in merged.items()}}
        ],
    }
