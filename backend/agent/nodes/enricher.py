"""Phase 2.5: LLM-based enrichment — Korean title translation, detailed summary, URL validation."""

import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

ENRICH_PROMPT = """You are a senior Korean business analyst at SK Enmove (a top lubricant company).
Your task: Translate and summarize this article for the MI newsletter.

Original title: {title}
Original snippet: {snippet}
Source: {source}
Country context: {country_name} lubricant market

Generate a JSON response with:
1. "title_kr": Korean title (natural, professional Korean — NOT literal translation. If already Korean, clean it up)
2. "summary_kr": Detailed Korean summary (3-5 sentences):
   - First sentence: What happened (who, what, when)
   - Second sentence: Key details (numbers, specifics)
   - Third sentence: Why this matters for lubricant sales strategy
   - Fourth sentence (if applicable): Potential impact on SK Enmove
   Keep it factual, data-driven, and actionable. No fluff.

Output JSON only: {{"title_kr": "...", "summary_kr": "..."}}
"""

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
}


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and accessible (quick HEAD request)."""
    if not url or url == "#":
        return False

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False

    # Google News redirect URLs are always valid
    if "news.google.com" in parsed.netloc:
        return True

    try:
        resp = requests.head(url, timeout=5, allow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code < 400
    except Exception:
        # If HEAD fails, still keep the URL (might block HEAD but allow GET)
        return True


def clean_google_news_title(title: str) -> str:
    """Remove source suffix from Google News titles like 'Title - Source Name'."""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts) == 2 and len(parts[1]) < 40:
            return parts[0].strip()
    return title.strip()


async def enrich_snippets(state: NewsletterState) -> dict:
    """Enrich articles: Korean title translation, detailed summary, URL validation."""
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
        country_name = COUNTRY_NAMES.get(country, country)

        for article in articles:
            # 1. URL validation
            url = article.get("url", "")
            if not is_valid_url(url):
                article["url_valid"] = False
                logger.info(f"[{country}] Invalid URL removed: {url[:60]}")
            else:
                article["url_valid"] = True

            # 2. Clean Google News title artifacts
            original_title = clean_google_news_title(article.get("title", ""))

            # 3. LLM enrichment — Korean title + detailed summary
            if client:
                try:
                    import asyncio
                    prompt = ENRICH_PROMPT.format(
                        title=original_title,
                        snippet=article.get("snippet", ""),
                        source=article.get("source", ""),
                        country_name=country_name,
                    )
                    response = await asyncio.to_thread(
                        client.messages.create,
                        model="claude-sonnet-4-20250514",
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()
                    if "{" in text:
                        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                        article["title_kr"] = data.get("title_kr", original_title)
                        article["summary_kr"] = data.get("summary_kr", article.get("snippet", ""))
                    else:
                        article["title_kr"] = original_title
                        article["summary_kr"] = text
                except Exception as e:
                    logger.warning(f"Enrichment failed: {e}")
                    article["title_kr"] = original_title
                    article["summary_kr"] = article.get("snippet", "")
            else:
                article["title_kr"] = original_title
                article["summary_kr"] = article.get("snippet", "")

            enriched_articles.append(article)

        enriched[country] = enriched_articles
        valid_count = sum(1 for a in enriched_articles if a.get("url_valid", True))
        logger.info(f"[{country}] Enriched {len(enriched_articles)} articles ({valid_count} valid URLs)")

    return {
        "enriched_articles": enriched,
        "current_phase": "grouping",
        "phase_status": {**state.get("phase_status", {}), "enrichment": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "enrichment", "ts": datetime.now().isoformat()}
        ],
    }
