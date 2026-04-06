"""Phase 2: Article scoring, tagging, and filtering using Anthropic Claude."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an MI analyst for SK Enmove, a lubricant company.
Score this article on a scale of 0-5 for relevance to FINISHED lubricant product sales strategy.

The core question: "Does this news affect how SK Enmove sells lubricants?"

Scoring criteria:
- 5: Direct competitor activity — new lubricant product launch, pricing change, promotion, distribution channel expansion, OEM partnership
- 4: Lubricant regulation/policy — API/ACEA/ILSAC specification update, import tariff change, environmental regulation affecting lubricant formulation
- 3: Forward industry trends DIRECTLY affecting lubricant demand:
     * Vehicle market: EV transition pace (affects ICE oil demand), hybrid growth (still needs oil), new car sales volume
     * Commercial vehicle/truck/bus fleet expansion (HDDO demand)
     * Marine/shipping fleet changes (marine lubricant demand)
     * Construction/mining equipment market (industrial lubricant demand)
     * Manufacturing/factory machinery trends (cutting fluid, hydraulic oil)
     * Motorcycle market growth in SEA (MCO demand)
     * Agricultural machinery/tractor market
- 2: Crude oil/base oil pricing trends affecting lubricant manufacturing cost
     * Refinery capacity changes impacting base oil supply
     * Group II/III base oil market shifts
- 1: Tangentially related — only if "anyone would obviously see the connection" to lubricants
- 0: Irrelevant — crypto, real estate, stock market, generic politics, entertainment, food, fashion

STRICT EXCLUSION rules:
- EV-only battery/charging articles with NO mention of lubricant/oil demand impact: score 0
- Pure stock market / financial instrument news: score 0
- Base oil-only upstream articles with no downstream sales implication: max 1 point
- Generic CSR/ESG/sustainability fluff: score 0
- Paid market research report previews (Mordor Intelligence, Allied Market Research, etc.): score 0

Article:
Title: {title}
Snippet: {snippet}
Source: {source}
Country: {country}
Domain: {domain}

Respond in JSON: {{"score": N, "sector": "윤활유동향|경쟁사활동|전방산업동향|윤활유규제", "reason": "brief Korean reason explaining sales relevance", "tags": ["tag1", "tag2"]}}
"""

NEGATIVE_KEYWORDS = [
    # Finance / stock
    "bitcoin", "cryptocurrency", "crypto", "dogecoin", "stock market",
    "dow jones", "s&p 500", "nasdaq", "wall street", "forex",
    "주식", "코인", "가상화폐",
    # Real estate
    "real estate", "property price", "부동산", "집값", "아파트",
    # Paid research
    "smartkarma", "grand view research", "mordor intelligence",
    "allied market research", "technavio", "imarc group", "indexbox",
    # Pure entertainment
    "celebrity", "entertainment", "k-pop", "drama",
    # Medical
    "한의과", "진료비", "의료비",
]


def quick_filter(article: Article) -> bool:
    """Fast negative keyword filter before LLM scoring."""
    text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()
    return not any(neg in text for neg in NEGATIVE_KEYWORDS)


async def score_single_article(article: Article, client) -> Article:
    """Score a single article using Claude."""
    try:
        prompt = SCORING_PROMPT.format(
            title=article.get("title", ""),
            snippet=article.get("snippet", ""),
            source=article.get("source", ""),
            country=article.get("country", ""),
            domain=article.get("collection_domain", ""),
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if "{" in text:
            data = json.loads(text[text.index("{"):text.rindex("}") + 1])
            article["score"] = data.get("score", 0)
            article["tags"] = data.get("tags", [])
            article["sector"] = data.get("sector", "윤활유동향")
            article["score_reason"] = data.get("reason", "")
        else:
            article["score"] = 0
    except Exception as e:
        logger.warning(f"Scoring failed for article: {e}")
        article["score"] = 0

    return article


async def score_articles(state: NewsletterState) -> dict:
    """Score and filter articles for all countries."""
    import anthropic

    merged = state.get("merged_articles", {})
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    scored: dict[str, list[Article]] = {}

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None
        logger.warning("ANTHROPIC_API_KEY not set, using keyword-based scoring fallback")

    for country, articles in merged.items():
        # Quick filter first
        filtered = [a for a in articles if quick_filter(a)]
        logger.info(f"[{country}] Quick filter: {len(articles)} -> {len(filtered)}")

        if client:
            # LLM scoring
            scored_articles = []
            for article in filtered:
                scored_article = await score_single_article(article, client)
                if scored_article.get("score", 0) >= 2:
                    scored_articles.append(scored_article)
        else:
            # Fallback: keep all that passed quick filter with default score
            for a in filtered:
                a["score"] = 3
            scored_articles = filtered

        # Sort by score descending
        scored_articles.sort(key=lambda a: a.get("score", 0), reverse=True)
        scored[country] = scored_articles[:20]  # Top 20 per country
        logger.info(f"[{country}] Scored: {len(scored[country])} articles kept")

    return {
        "scored_articles": scored,
        "current_phase": "enrichment",
        "phase_status": {**state.get("phase_status", {}), "scoring": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "scoring", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in scored.items()}}
        ],
    }
