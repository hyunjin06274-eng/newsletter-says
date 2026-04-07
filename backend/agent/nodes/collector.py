"""Phase 1: News collection with LLM-driven dynamic query expansion."""

import json
import logging
import os
from datetime import datetime, timedelta

import requests

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

DOMAINS = ["macro", "industry", "competitor", "lubricant"]

# Static fallback templates per domain
DOMAIN_QUERY_TEMPLATES = {
    "macro": [
        "{keyword} crude oil price base oil supply",
        "{keyword} base oil Group II Group III refinery",
    ],
    "industry": [
        "{keyword} automobile sales EV transition hybrid",
        "{keyword} commercial vehicle truck fleet",
        "{keyword} construction mining equipment machinery",
        "{keyword} marine shipping fleet vessel",
        "{keyword} motorcycle market scooter",
        "{keyword} agricultural tractor machinery",
    ],
    "competitor": [
        "{keyword} lubricant new product launch",
        "{keyword} engine oil promotion pricing",
        "{keyword} lubricant distribution channel OEM",
    ],
    "lubricant": [
        "{keyword} lubricant API ACEA ILSAC specification",
        "{keyword} lubricant import tariff regulation",
        "{keyword} engine oil market aftermarket",
    ],
}

# LLM prompt for dynamic query generation
DYNAMIC_QUERY_PROMPT = """You are a search query specialist for lubricant industry market intelligence.

Generate 8 diverse search queries for the "{domain}" domain in {country_name}.
These queries will be used to find news articles on Google News.

Domain focus:
- macro: crude oil prices, base oil supply, refinery output, FX rates affecting lubricant costs
- industry: vehicle sales (ICE, hybrid, EV transition pace), commercial trucks, construction equipment, marine, motorcycle, agricultural machinery — ONLY topics that directly affect lubricant demand
- competitor: competitor lubricant brands (product launches, promotions, channel strategy, OEM partnerships, SNS campaigns)
- lubricant: lubricant specifications (API/ACEA/ILSAC), tariffs, regulations, market size, aftermarket trends

Country context: {country_name}
Known competitors in this market: {competitors}

IMPORTANT:
- Include queries in BOTH English AND local language ({local_lang})
- Make queries specific enough to find relevant articles (not too broad)
- Every query must have a clear, obvious connection to lubricant finished product sales
- Include niche sources: industry trade publications, OEM announcements, regulatory bodies

Output a JSON array of 8 search query strings. No explanation, just the array.
"""

COUNTRY_INFO = {
    "KR": {"name": "South Korea", "lang": "Korean",
           "competitors": "SK ZIC, GS Kixx, S-OIL, Shell Korea, Castrol Korea, Valvoline"},
    "RU": {"name": "Russia", "lang": "Russian",
           "competitors": "Lukoil, Gazpromneft G-Energy, Rosneft, Shell Russia, Castrol Russia"},
    "VN": {"name": "Vietnam", "lang": "Vietnamese",
           "competitors": "Petrolimex PLC, Shell Vietnam, Castrol Vietnam, Total Vietnam, BP Vietnam"},
    "TH": {"name": "Thailand", "lang": "Thai",
           "competitors": "PTT Lubricants, Shell Thailand, Castrol Thailand, Caltex, Valvoline Thailand"},
    "PH": {"name": "Philippines", "lang": "Filipino/English",
           "competitors": "Petron, Shell Philippines, Caltex Philippines, Total Philippines"},
    "PK": {"name": "Pakistan", "lang": "Urdu/English",
           "competitors": "PSO, Shell Pakistan, Attock Petroleum, Caltex Pakistan, Total Parco"},
}

# when:{days}d restricts to recent articles only
# Two variants: English and local language results
GOOGLE_NEWS_RSS_EN = "https://news.google.com/rss/search?q={query}+when:{days}d&hl=en&gl={country}&ceid={country}:en"
GOOGLE_NEWS_RSS_LOCAL = {
    "KR": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko",
    "RU": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=ru&gl=RU&ceid=RU:ru",
    "VN": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=vi&gl=VN&ceid=VN:vi",
    "TH": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=th&gl=TH&ceid=TH:th",
    "PH": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=en&gl=PH&ceid=PH:en",
    "PK": "https://news.google.com/rss/search?q={query}+when:{days}d&hl=en&gl=PK&ceid=PK:en",
}


def generate_dynamic_queries(country: str, domain: str) -> list[str]:
    """Use LLM to generate diverse, relevant search queries."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        info = COUNTRY_INFO.get(country, {"name": country, "lang": "English", "competitors": ""})

        prompt = DYNAMIC_QUERY_PROMPT.format(
            domain=domain,
            country_name=info["name"],
            competitors=info["competitors"],
            local_lang=info["lang"],
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if "[" in text and "]" in text:
            try:
                queries = json.loads(text[text.index("["):text.rindex("]") + 1])
            except json.JSONDecodeError:
                queries = []
            logger.info(f"[{country}/{domain}] LLM generated {len(queries)} dynamic queries")
            print(f"[{country}/{domain}] LLM generated {len(queries)} dynamic queries", flush=True)
            return queries
    except Exception as e:
        logger.warning(f"[{country}/{domain}] Dynamic query generation failed: {e}")

    return []


def fetch_google_news_rss(query: str, country: str, max_results: int = 15, days: int = 30) -> list[Article]:
    """Fetch articles from Google News RSS — both English and local language."""
    import feedparser

    urls = [GOOGLE_NEWS_RSS_EN.format(query=query.replace(" ", "+"), country=country, days=days)]
    local_template = GOOGLE_NEWS_RSS_LOCAL.get(country)
    if local_template:
        urls.append(local_template.format(query=query.replace(" ", "+"), days=days))
    articles = []

    for url in urls:
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
    """Collect news for one country-domain pair using static + dynamic queries."""
    articles = []

    # 1. Static template queries (always run as baseline)
    templates = DOMAIN_QUERY_TEMPLATES.get(domain, ["{keyword}"])
    for kw in keywords[:4]:
        for template in templates:
            query = template.format(keyword=kw)
            results = fetch_google_news_rss(query, country, max_results=8, days=days)
            for article in results:
                article["collection_domain"] = domain
            articles.extend(results)

    # 2. LLM-generated dynamic queries (broader, more creative exploration)
    dynamic_queries = generate_dynamic_queries(country, domain)
    for query in dynamic_queries:
        results = fetch_google_news_rss(query, country, max_results=10, days=days)
        for article in results:
            article["collection_domain"] = domain
            article["query_source"] = "dynamic_llm"
        articles.extend(results)

    logger.info(
        f"[{country}/{domain}] Collected {len(articles)} articles "
        f"(static + {len(dynamic_queries)} dynamic queries)"
    )
    return articles


async def collect_news(state: NewsletterState) -> dict:
    """Collect news across all countries and domains."""
    countries = state["countries"]
    keywords = state.get("keywords", {})
    days = state.get("days", 30)
    raw_articles: dict[str, list[Article]] = {}

    for country in countries:
        country_kw = keywords.get(country, [])
        all_articles = []

        for domain in DOMAINS:
            domain_articles = await collect_for_country_domain(
                country, domain, country_kw, days
            )
            all_articles.extend(domain_articles)

        raw_articles[country] = all_articles
        logger.info(f"[{country}] Total collected: {len(all_articles)} articles")
        print(f"[{country}] Total collected: {len(all_articles)} articles", flush=True)

    return {
        "raw_articles": raw_articles,
        "current_phase": "merge",
        "phase_status": {**state.get("phase_status", {}), "collection": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "collection", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in raw_articles.items()}}
        ],
    }
