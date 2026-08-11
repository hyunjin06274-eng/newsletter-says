"""Build a UnifiedIssue from per-country grouped articles + LLM-generated content.

Called inside write_newsletter() after LLM insights/recommendations are generated.
No LLM calls here — pure data transformation.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from backend.agent.state import Article, CountrySection, GlobalSection, UnifiedIssue

logger = logging.getLogger(__name__)

# ── URL normalisation ─────────────────────────────────────────────────────────

# Query params that carry tracking info but not content identity.
# Stripped before URL comparison so "article.html?utm_source=x" == "article.html".
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "yclid", "from", "_ga",
})


def _normalize_url(url: str) -> str:
    """Return a canonical URL string for dedup comparison.

    Rules applied (in order):
    1. Scheme normalised to https
    2. Netloc lowercased
    3. Trailing slash stripped from path
    4. Tracking query params removed (see _TRACKING_PARAMS)
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(filtered, doseq=True)
        path = parsed.path.rstrip("/")
        return urlunparse(("https", parsed.netloc.lower(), path, parsed.params, query, ""))
    except Exception:
        return url


# ── Dedup helpers ─────────────────────────────────────────────────────────────


def _title_similarity(t1: str, t2: str) -> float:
    """SequenceMatcher ratio between two lowercased titles (0.0 – 1.0)."""
    if not t1 or not t2:
        return 0.0
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def _is_duplicate(
    article: Article,
    seen_urls: set[str],
    seen_titles: list[str],
) -> bool:
    """Return True if article is a duplicate of one already registered.

    Dedup criteria (evaluated in priority order):
    1. URL match — normalised URL exact match
    2. Title similarity >= 0.8 — same story published by different outlet
    """
    norm_url = _normalize_url(article.get("url", ""))
    if norm_url and norm_url in seen_urls:
        return True

    title = article.get("title_kr") or article.get("title", "")
    for seen in seen_titles:
        if _title_similarity(title, seen) >= 0.8:
            return True

    return False


def _register(
    article: Article,
    seen_urls: set[str],
    seen_titles: list[str],
) -> None:
    """Add article's URL and title to the seen sets."""
    norm_url = _normalize_url(article.get("url", ""))
    if norm_url:
        seen_urls.add(norm_url)
    title = article.get("title_kr") or article.get("title", "")
    if title:
        seen_titles.append(title)


# ── Main builder ──────────────────────────────────────────────────────────────


def build_unified_issue(
    run_id: str,
    date_str: str,
    countries: list[str],
    grouped_articles: dict[str, list[Article]],
    insights_by_country: dict[str, list[str]],
    recommendations_by_country: dict[str, list[str]],
    kpi_data: dict[str, dict],
) -> UnifiedIssue:
    """Assemble a UnifiedIssue from per-country pipeline output.

    Algorithm
    ---------
    Step 1 — Global section
        Collect all articles where scope == "global" from every country's list.
        Sort by score descending, then dedup by URL/title (highest-score variant kept).

    Step 2 — Country sections
        For each country, take articles where scope == "local".
        Remove any article already present in the global section (URL/title dedup).
        Countries with zero local articles still get a CountrySection (empty articles
        list) so the UI can show an "no news this issue" placeholder.

    Step 3 — Annotate countries field on each article
        "global" → countries = ["GLOBAL"]
        "local"  → countries = [article["country"]]
    """
    # ── Step 1: Global section ────────────────────────────────────────────────
    global_seen_urls: set[str] = set()
    global_seen_titles: list[str] = []
    global_articles: list[Article] = []

    # Gather all global-scope articles across every country, best score first
    all_global: list[Article] = []
    for cc in countries:
        for a in grouped_articles.get(cc, []):
            if a.get("scope") == "global":
                all_global.append(a)
    all_global.sort(key=lambda x: x.get("score", 0), reverse=True)

    for a in all_global:
        if not _is_duplicate(a, global_seen_urls, global_seen_titles):
            annotated = dict(a)
            annotated["countries"] = ["GLOBAL"]
            global_articles.append(annotated)  # type: ignore[arg-type]
            _register(a, global_seen_urls, global_seen_titles)

    logger.info(f"[issue_builder] Global section: {len(global_articles)} articles")

    # ── Step 2: Country sections ──────────────────────────────────────────────
    country_sections: dict[str, CountrySection] = {}

    for cc in countries:
        articles = grouped_articles.get(cc, [])
        local_articles: list[Article] = []

        # Start dedup sets from global section so local articles can't repeat globals
        local_seen_urls: set[str] = set(global_seen_urls)
        local_seen_titles: list[str] = list(global_seen_titles)

        for a in articles:
            if a.get("scope") != "local":
                continue
            if _is_duplicate(a, local_seen_urls, local_seen_titles):
                continue
            annotated = dict(a)
            annotated["countries"] = [cc]
            local_articles.append(annotated)  # type: ignore[arg-type]
            _register(a, local_seen_urls, local_seen_titles)

        country_sections[cc] = CountrySection(
            country=cc,
            articles=local_articles,
            insights=insights_by_country.get(cc, []),
            recommendations=recommendations_by_country.get(cc, []),
            kpi_data=kpi_data.get(cc, {}),
        )
        logger.info(f"[issue_builder] {cc}: {len(local_articles)} local articles")

    return UnifiedIssue(
        run_id=run_id,
        date_str=date_str,
        countries=countries,
        global_section=GlobalSection(articles=global_articles),
        country_sections=country_sections,
    )


def get_recipient_default_country(
    recipient_country: str | None,
    available_countries: list[str],
    fallback: str = "KR",
) -> str:
    """Resolve the default tab country for a given recipient.

    Priority:
    1. recipient_country if it is in available_countries
    2. fallback ("KR" by default) if it is in available_countries
    3. first country in available_countries
    """
    if recipient_country and recipient_country in available_countries:
        return recipient_country
    if fallback in available_countries:
        return fallback
    return available_countries[0] if available_countries else fallback
