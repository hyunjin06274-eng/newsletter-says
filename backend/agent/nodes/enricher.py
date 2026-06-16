"""Phase 2.5: LLM-based enrichment — Korean title translation, detailed summary, URL validation, body extraction."""

import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)


def resolve_google_news_url(url: str) -> str:
    """Decode Google News redirect URL to the actual article URL.

    Google News RSS provides URLs like https://news.google.com/rss/articles/CBMi...
    which are protobuf-encoded redirects. This function decodes them to real URLs.
    Returns the original URL if decoding fails.
    """
    if not url or "news.google.com" not in url:
        return url

    try:
        from googlenewsdecoder import new_decoderv1
        result = new_decoderv1(url, interval=3)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        logger.debug(f"Google News URL decode failed: {e}")

    return url


def fetch_article_body(url: str, max_chars: int = 1500) -> str:
    """Extract article body text from URL using trafilatura.

    Returns up to max_chars of the article body, or empty string on failure.
    """
    if not url or url == "#":
        return ""

    try:
        import trafilatura

        resp = requests.get(
            url, timeout=8, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if resp.status_code >= 400:
            return ""

        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        if text:
            return text[:max_chars]
    except Exception as e:
        logger.debug(f"Body extraction failed for {url[:60]}: {e}")

    return ""

ENRICH_PROMPT = """You are a senior Korean business analyst at SK Enmove (a top lubricant company).
Your task: Translate and summarize this article for the MI newsletter.

Original title: {title}
Original snippet: {snippet}
Article body (if available): {body_text}
Source: {source}
Country context: {country_name} lubricant market

=== CRITICAL RULES ===
1. NEVER reinterpret or replace geopolitical events mentioned in the article.
   - If the article mentions a specific war, conflict, or political event, use EXACTLY that reference.
   - Do NOT substitute one conflict for another (e.g., do NOT change "Iran conflict" to "Ukraine war").
2. Stay strictly within the facts presented in the article. Do NOT add external context or assumptions.
3. The target country is {country_name}. Frame the impact analysis ONLY for {country_name}'s lubricant market.
4. If article body is provided, you MUST use specific numbers, model names, company names, and data from it.
5. NEVER use hedging phrases like "본문 미확보", "확인이 필요하다", "단정하기 어렵다", "정확한 수치는 알 수 없다".
   - If information is limited, write what you know and end with "상세 내용은 원문 참조" instead.
6. Output MUST be in Korean. Do NOT output English text in title_kr or summary_kr.

Generate a JSON response with:
1. "title_kr": Korean title (natural, professional Korean — NOT literal translation. If already Korean, clean it up)
2. "summary_kr": Detailed Korean summary (3-5 sentences):
   - First sentence: What happened (who, what, when) — use EXACT facts from the article
   - Second sentence: Key details (numbers, specifics from body if available)
   - Third sentence: Why this matters for lubricant sales strategy in {country_name}
   - Fourth sentence (if applicable): Potential impact on SK Enmove
   Keep it factual, data-driven, and actionable. No fluff. No external inference.

IMPORTANT: Output ONLY valid JSON. No explanation, no markdown, no code fences.
Start your response with {{ and end with }}.
Output JSON only: {{"title_kr": "...", "summary_kr": "..."}}
"""

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
    "GCC": "GCC(걸프협력회의)",
    "CN": "중국", "US": "미국", "IN": "인도", "JP": "일본",
}


def is_korean(text: str) -> bool:
    """Check if text contains meaningful Korean content (at least 30% Korean chars)."""
    if not text:
        return False
    korean_chars = len(re.findall(r'[가-힣]', text))
    total_chars = len(re.findall(r'[^\s\d\W]', text))  # letters only (no spaces/digits/punct)
    if total_chars == 0:
        return False
    return korean_chars / total_chars >= 0.3


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and accessible (quick HEAD request)."""
    if not url or url == "#":
        return False

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False

    # Google News redirect URLs — still valid as fallback (browser can resolve them)
    if "news.google.com" in parsed.netloc:
        return True  # Will be resolved to real URL in enrich_snippets()

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
        total = len(articles)
        print(f"📝 [{country}] Enriching {total} articles...", flush=True)

        for idx, article in enumerate(articles, 1):
            # 1. Resolve Google News redirect URL to actual article URL
            url = article.get("url", "")
            if url and "news.google.com" in url:
                try:
                    import asyncio
                    resolved = await asyncio.to_thread(resolve_google_news_url, url)
                    if resolved != url:
                        article["google_news_url"] = url  # Keep original for reference
                        article["url"] = resolved
                        url = resolved
                        logger.debug(f"[{country}] Resolved URL: {resolved[:80]}")
                except Exception:
                    pass

            # 2. URL validation (now on the real URL)
            if not is_valid_url(url):
                article["url_valid"] = False
                logger.info(f"[{country}] Invalid URL removed: {url[:60]}")
                print(f"[{country}] Invalid URL removed: {url[:60]}", flush=True)
            else:
                article["url_valid"] = True

            # 3. Clean Google News title artifacts
            original_title = clean_google_news_title(article.get("title", ""))

            # 4. Fetch article body for richer summaries
            body_text = ""
            if url and url != "#":
                try:
                    import asyncio
                    body_text = await asyncio.to_thread(fetch_article_body, url)
                    if body_text:
                        print(f"  [{country}] Body extracted ({len(body_text)} chars): {original_title[:40]}", flush=True)
                except Exception:
                    pass

            # 4. LLM enrichment — Korean title + detailed summary
            if client:
                try:
                    import asyncio
                    prompt = ENRICH_PROMPT.format(
                        title=original_title,
                        snippet=article.get("snippet", ""),
                        body_text=body_text if body_text else "(본문 미확보 — snippet만 활용)",
                        source=article.get("source", ""),
                        country_name=country_name,
                    )
                    response = await asyncio.to_thread(
                        client.messages.create,
                        model="claude-sonnet-4-6",
                        max_tokens=800,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()
                    start, end = text.find("{"), text.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        data = json.loads(text[start:end + 1])
                        title_kr = data.get("title_kr", original_title)
                        summary_kr = data.get("summary_kr", article.get("snippet", ""))

                        # Verify Korean output — retry once if English
                        if not is_korean(title_kr) or not is_korean(summary_kr):
                            logger.info(f"[{country}] Non-Korean output, retrying: {original_title[:40]}")
                            retry_prompt = prompt + "\n\nIMPORTANT: Your previous output was in English. You MUST output title_kr and summary_kr in Korean (한국어). Retry now."
                            retry_resp = await asyncio.to_thread(
                                client.messages.create,
                                model="claude-sonnet-4-6",
                                max_tokens=500,
                                messages=[{"role": "user", "content": retry_prompt}],
                            )
                            retry_text = retry_resp.content[0].text.strip()
                            rs, re_ = retry_text.find("{"), retry_text.rfind("}")
                            if rs != -1 and re_ != -1 and re_ > rs:
                                retry_data = json.loads(retry_text[rs:re_ + 1])
                                title_kr = retry_data.get("title_kr", title_kr)
                                summary_kr = retry_data.get("summary_kr", summary_kr)

                        article["title_kr"] = title_kr
                        article["summary_kr"] = summary_kr
                    else:
                        article["title_kr"] = original_title
                        article["summary_kr"] = text
                        article["_enrich_failed"] = True
                except Exception as e:
                    logger.warning(f"Enrichment failed: {e}")
                    article["title_kr"] = original_title
                    article["summary_kr"] = article.get("snippet", "")
                    article["_enrich_failed"] = True
            else:
                article["title_kr"] = original_title
                article["summary_kr"] = article.get("snippet", "")
                article["_enrich_failed"] = True

            enriched_articles.append(article)

        enriched[country] = enriched_articles
        valid_count = sum(1 for a in enriched_articles if a.get("url_valid", True))
        logger.info(f"[{country}] Enriched {len(enriched_articles)} articles ({valid_count} valid URLs)")
        print(f"[{country}] Enriched {len(enriched_articles)} articles ({valid_count} valid URLs)", flush=True)

    return {
        "enriched_articles": enriched,
        "current_phase": "grouping",
        "phase_status": {**state.get("phase_status", {}), "enrichment": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "enrichment", "ts": datetime.now().isoformat()}
        ],
    }
