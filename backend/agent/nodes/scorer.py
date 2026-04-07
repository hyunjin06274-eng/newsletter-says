"""Phase 2: Article scoring, tagging, and filtering using Anthropic Claude."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an MI analyst for SK Enmove, a lubricant company.
Score this article on a scale of 0-30 for relevance to FINISHED lubricant product sales strategy.

The core question: "Does this news affect how SK Enmove sells lubricants?"

Scoring dimensions (each 0-10, total max 30):

A. Sales Relevance (0-10):
- 10: Direct competitor new product/promotion/channel in target country
- 8: Lubricant regulation change (API/ACEA/tariff) in target country
- 6: Vehicle/equipment sales data directly affecting lubricant demand
- 4: Base oil/crude price affecting manufacturing cost
- 2: Tangential industry news
- 0: Irrelevant

B. Country Specificity (0-10):
- 10: Exclusively about target country market, local companies, local data
- 7: Primarily about target country with some global context
- 4: Regional (Asia/Europe) news with some target country relevance
- 1: Pure global news with indirect country impact
- 0: About a different specific country

C. Actionability (0-10):
- 10: Requires immediate response (competitor launch, regulation deadline)
- 7: Should influence quarterly planning
- 4: Good-to-know market intelligence
- 2: Background context only
- 0: No actionable insight
- 0: Irrelevant — crypto, real estate, stock market, generic politics, entertainment, food, fashion

STRICT EXCLUSION rules:
- EV-only battery/charging articles with NO mention of lubricant/oil demand impact: score 0
- Pure stock market / financial instrument news: score 0
- Base oil-only upstream articles with no downstream sales implication: max 1 point
- Generic CSR/ESG/sustainability fluff: score 0
- Paid market research report previews (Mordor Intelligence, Allied Market Research, etc.): score 0

CRITICAL — COUNTRY vs GLOBAL classification:
Target country: {country}

Classify scope:
- "local" = specifically about {country} market
- "global" = industry-wide, affects all markets
- "other_country" = about a DIFFERENT country → total score 0

Article:
Title: {title}
Snippet: {snippet}
Source: {source}
Target country: {country}
Domain: {domain}

Respond in JSON: {{"score_sales": 0-10, "score_country": 0-10, "score_action": 0-10, "scope": "local|global|other_country", "sector": "윤활유동향|경쟁사활동|전방산업동향|윤활유규제", "reason": "brief Korean reason", "tags": ["tag1"]}}
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
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        return False
    # Filter out market research report spam (preview/teaser pages)
    report_spam = [
        "market size", "market share", "market forecast", "market analysis",
        "market report", "cagr", "billion by 20", "million by 20",
        "research report", "industry report", "market outlook",
        "시장 규모", "시장 전망", "시장 분석 보고서",
    ]
    spam_count = sum(1 for r in report_spam if r in text)
    if spam_count >= 2:
        return False  # Likely a paid research report preview
    return True


async def score_single_article(article: Article, client) -> Article:
    """Score a single article using Claude."""
    import asyncio
    try:
        prompt = SCORING_PROMPT.format(
            title=article.get("title", ""),
            snippet=article.get("snippet", ""),
            source=article.get("source", ""),
            country=article.get("country", ""),
            domain=article.get("collection_domain", ""),
        )

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if "{" in text:
            data = json.loads(text[text.index("{"):text.rindex("}") + 1])
            scope = data.get("scope", "local")
            if scope == "other_country":
                article["score"] = 0
                article["score_reason"] = "Other country - rejected"
            else:
                s1 = min(data.get("score_sales", 0), 10)
                s2 = min(data.get("score_country", 0), 10)
                s3 = min(data.get("score_action", 0), 10)
                article["score"] = s1 + s2 + s3  # 0-30 total
                article["score_sales"] = s1
                article["score_country"] = s2
                article["score_action"] = s3
                article["score_reason"] = data.get("reason", "")
            article["tags"] = data.get("tags", [])
            article["sector"] = data.get("sector", "윤활유동향")
            article["scope"] = scope
            if scope == "global":
                article["tags"] = list(set(article["tags"] + ["글로벌"]))
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
        # Limit to 30 articles max for LLM scoring (saves time + cost)
        to_score = filtered[:30]
        print(f"📊 [{country}] Quick filter: {len(articles)} -> {len(filtered)}, scoring top {len(to_score)}", flush=True)

        if client:
            scored_articles = []
            for i, article in enumerate(to_score, 1):
                title_short = article.get("title", "")[:40]
                print(f"  📊 [{country}] Scoring {i}/{len(to_score)}: {title_short}...", flush=True)
                scored_article = await score_single_article(article, client)
                s = scored_article.get("score", 0)
                if s >= 10:
                    scored_articles.append(scored_article)
                    print(f"  📊 [{country}] -> score={s} ✓", flush=True)
                else:
                    print(f"  📊 [{country}] -> score={s} ✗ (filtered)", flush=True)
        else:
            for a in to_score:
                a["score"] = 3
            scored_articles = to_score

        scored_articles.sort(key=lambda a: a.get("score", 0), reverse=True)
        scored[country] = scored_articles[:15]
        print(f"📊 [{country}] ✅ Scoring done: {len(scored[country])} articles kept", flush=True)

    return {
        "scored_articles": scored,
        "current_phase": "enrichment",
        "phase_status": {**state.get("phase_status", {}), "scoring": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "scoring", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in scored.items()}}
        ],
    }
