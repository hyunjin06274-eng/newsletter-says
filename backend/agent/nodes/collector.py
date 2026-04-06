"""Phase 1: News collection across 4 domains per country."""

import logging
import asyncio
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

DOMAINS = ["macro", "industry", "competitor", "lubricant"]

DOMAIN_QUERY_TEMPLATES = {
    "macro": "{keyword} oil price crude supply chain",
    "industry": "{keyword} automobile EV OEM sales",
    "competitor": "{keyword} lubricant competitor promotion",
    "lubricant": "{keyword} lubricant API ACEA regulation tariff",
}

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en&gl={country}&ceid={country}:en"


def fetch_google_news_rss(query: str, country: str, max_results: int = 20) -> list[Article]:
    """Fetch articles from Google News RSS feed."""
    import feedparser

    url = GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"), country=country)
    articles = []

    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_results]:
            articles.append(Article(
                url=entry.get("link", ""),
                title=entry.get("title", ""),
                snippet=entry.get("summary", ""),
                source=entry.get("source", {}).get("title", "Unknown"),
                published_date=entry.get("published", ""),
                country=country,
            ))
    except Exception as e:
        logger.warning(f"RSS fetch failed for {query}/{country}: {e}")

    return articles


async def collect_for_country_domain(
    country: str, domain: str, keywords: list[str], days: int
) -> list[Article]:
    """Collect news for one country-domain pair."""
    articles = []
    template = DOMAIN_QUERY_TEMPLATES.get(domain, "{keyword}")

    for kw in keywords[:5]:  # Limit keywords per domain
        query = template.format(keyword=kw)
        results = fetch_google_news_rss(query, country, max_results=10)
        for article in results:
            article["collection_domain"] = domain
        articles.extend(results)

    logger.info(f"[{country}/{domain}] Collected {len(articles)} articles")
    return articles


async def collect_news(state: NewsletterState) -> dict:
    """Collect news across all countries and domains in parallel."""
    countries = state["countries"]
    keywords = state.get("keywords", {})
    days = state.get("days", 30)
    raw_articles: dict[str, list[Article]] = {}

    for country in countries:
        country_kw = keywords.get(country, [])
        all_articles = []

        # Collect from all 4 domains
        for domain in DOMAINS:
            domain_articles = await collect_for_country_domain(
                country, domain, country_kw, days
            )
            all_articles.extend(domain_articles)

        raw_articles[country] = all_articles
        logger.info(f"[{country}] Total collected: {len(all_articles)} articles")

    return {
        "raw_articles": raw_articles,
        "current_phase": "merge",
        "phase_status": {**state.get("phase_status", {}), "collection": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "collection", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in raw_articles.items()}}
        ],
    }
