"""Filter previously published articles from the scored article pool.

Runs after the scoring phase. Queries the last 3 weeks of completed newsletter
runs from Supabase, collects every article URL / title that was actually sent,
and removes matching articles from scored_articles so they don't appear in the
current issue again.

Matching criteria (same logic as issue_builder dedup):
  1. Normalised URL exact match
  2. Title similarity >= 0.85  (slightly stricter than intra-issue dedup)
     — compared against both title_kr and title fields
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

# Tracking params stripped before URL comparison (same set as issue_builder)
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "yclid", "from", "_ga",
})

# How many days back to look for previously published articles
_HISTORY_DAYS = 21  # 3 weeks

# Title similarity threshold — slightly stricter than intra-issue dedup (0.80)
_TITLE_SIM_THRESHOLD = 0.85


# ── URL / title helpers ───────────────────────────────────────────────────────


def _normalize_url(url: str) -> str:
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


def _title_sim(t1: str, t2: str) -> float:
    if not t1 or not t2:
        return 0.0
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


# ── History loader ────────────────────────────────────────────────────────────


def _load_published_history(days: int = _HISTORY_DAYS) -> tuple[set[str], list[str]]:
    """Return (published_urls, published_titles) from completed runs in the past `days` days.

    Queries Supabase for completed runs, extracts all article urls / title_kr / title
    from their unified_issue. Returns empty sets on any failure (fail-open: better
    to risk a duplicate than to block the pipeline).
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        logger.warning("[history_filter] SUPABASE_URL/KEY not set — skipping history check")
        return set(), []

    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        import requests as _req
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        resp = _req.get(
            f"{supabase_url}/rest/v1/runs",
            params={
                "status": "eq.completed",
                "created_at": f"gte.{cutoff}",
                "select": "id,created_at,unified_issue",
                "order": "created_at.desc",
            },
            headers=headers,
            timeout=20,
        )
        if not resp.ok:
            logger.warning(f"[history_filter] Supabase query failed: {resp.status_code}")
            return set(), []

        rows = resp.json()
        if not rows:
            logger.info("[history_filter] No completed runs in the past 3 weeks")
            return set(), []

        published_urls: set[str] = set()
        published_titles: list[str] = []

        for row in rows:
            issue = row.get("unified_issue") or {}
            # Handle both dict (JSONB) and string (legacy) formats
            if isinstance(issue, str):
                import json
                try:
                    issue = json.loads(issue)
                except Exception:
                    continue

            run_id_short = str(row.get("id", ""))[:8]

            # Global section articles
            for a in issue.get("global_section", {}).get("articles", []):
                _register_article(a, published_urls, published_titles)

            # Country section articles
            for cc, cs in issue.get("country_sections", {}).items():
                for a in cs.get("articles", []):
                    _register_article(a, published_urls, published_titles)

        logger.info(
            f"[history_filter] Loaded {len(rows)} past runs → "
            f"{len(published_urls)} unique URLs, {len(published_titles)} titles"
        )
        print(
            f"📚 [history_filter] Past {days}d: {len(rows)} runs, "
            f"{len(published_urls)} published URLs loaded",
            flush=True,
        )
        return published_urls, published_titles

    except Exception as e:
        logger.warning(f"[history_filter] Failed to load history (fail-open): {e}")
        return set(), []


def _register_article(article: dict, urls: set[str], titles: list[str]) -> None:
    norm = _normalize_url(article.get("url", ""))
    if norm:
        urls.add(norm)
    for key in ("title_kr", "title"):
        t = article.get(key, "")
        if t:
            titles.append(t)
            break  # only add one title variant per article


def _is_previously_published(article: dict, published_urls: set[str], published_titles: list[str]) -> bool:
    """Return True if the article matches a previously published article."""
    norm = _normalize_url(article.get("url", ""))
    if norm and norm in published_urls:
        return True

    # Compare both title_kr and title against published titles
    for key in ("title_kr", "title"):
        t = article.get(key, "")
        if t and any(_title_sim(t, pt) >= _TITLE_SIM_THRESHOLD for pt in published_titles):
            return True

    return False


# ── LangGraph node ────────────────────────────────────────────────────────────


async def filter_published_articles(state: NewsletterState) -> dict:
    """LangGraph node: remove previously published articles from scored_articles.

    Placed between 'score' and 'enrich' in the pipeline. Fails open — if
    history cannot be loaded, the full scored article pool is kept unchanged.
    """
    scored = state.get("scored_articles", {})
    if not scored:
        return {}

    published_urls, published_titles = _load_published_history(_HISTORY_DAYS)

    if not published_urls and not published_titles:
        # No history available — nothing to filter
        return {
            "current_phase": "history_filter",
            "phase_status": {**state.get("phase_status", {}), "history_filter": "skipped"},
        }

    filtered: dict = {}
    total_before = sum(len(v) for v in scored.values())
    total_removed = 0

    for country, articles in scored.items():
        kept = []
        for a in articles:
            if _is_previously_published(a, published_urls, published_titles):
                total_removed += 1
                logger.info(
                    f"[history_filter] [{country}] Removed (published): "
                    f"'{a.get('title', '')[:60]}'"
                )
            else:
                kept.append(a)
        filtered[country] = kept
        if len(kept) < len(articles):
            print(
                f"  📚 [{country}] History filter: {len(articles) - len(kept)} removed, "
                f"{len(kept)} kept",
                flush=True,
            )

    total_after = total_before - total_removed
    print(
        f"📚 [history_filter] Done: {total_removed}/{total_before} articles removed "
        f"({total_after} remaining)",
        flush=True,
    )

    return {
        "scored_articles": filtered,
        "current_phase": "history_filter",
        "phase_status": {**state.get("phase_status", {}), "history_filter": "done"},
    }
