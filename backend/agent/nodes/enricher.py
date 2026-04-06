"""Phase 2.5: LLM-based snippet enrichment with Korean summaries."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

ENRICH_PROMPT = """You are a Korean business analyst for SK Enmove (lubricant company).
Summarize this article in Korean (2-3 sentences) focusing on implications for lubricant sales strategy.

Title: {title}
Snippet: {snippet}
Source: {source}
Country context: {country}

Output Korean summary only, no JSON wrapper.
"""


async def enrich_snippets(state: NewsletterState) -> dict:
    """Enrich article snippets with Korean LLM summaries."""
    import anthropic

    scored = state.get("scored_articles", {})
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    enriched: dict[str, list[Article]] = {}

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None
        logger.warning("ANTHROPIC_API_KEY not set, skipping enrichment")

    for country, articles in scored.items():
        enriched_articles = []
        for article in articles:
            if client:
                try:
                    prompt = ENRICH_PROMPT.format(
                        title=article.get("title", ""),
                        snippet=article.get("snippet", ""),
                        source=article.get("source", ""),
                        country=country,
                    )
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    article["summary_kr"] = response.content[0].text.strip()
                except Exception as e:
                    logger.warning(f"Enrichment failed: {e}")
                    article["summary_kr"] = article.get("snippet", "")
            else:
                article["summary_kr"] = article.get("snippet", "")

            enriched_articles.append(article)

        enriched[country] = enriched_articles
        logger.info(f"[{country}] Enriched {len(enriched_articles)} articles")

    return {
        "enriched_articles": enriched,
        "current_phase": "grouping",
        "phase_status": {**state.get("phase_status", {}), "enrichment": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "enrichment", "ts": datetime.now().isoformat()}
        ],
    }
