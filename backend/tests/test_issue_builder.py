"""Unit tests for issue_builder.py

Run:
    cd newsletter-saas
    python -m pytest backend/tests/test_issue_builder.py -v
"""

import pytest

from backend.agent.nodes.issue_builder import (
    _is_duplicate,
    _normalize_url,
    _register,
    _title_similarity,
    build_unified_issue,
    get_recipient_default_country,
)
from backend.agent.state import Article


# ── _normalize_url ────────────────────────────────────────────────────────────


def test_normalize_url_strips_utm():
    url = "https://example.com/article?utm_source=newsletter&utm_medium=email&id=123"
    assert _normalize_url(url) == "https://example.com/article?id=123"


def test_normalize_url_http_to_https():
    assert _normalize_url("http://example.com/page") == "https://example.com/page"


def test_normalize_url_strips_trailing_slash():
    assert _normalize_url("https://example.com/article/") == "https://example.com/article"


def test_normalize_url_lowercases_netloc():
    assert _normalize_url("https://Example.COM/page") == "https://example.com/page"


def test_normalize_url_empty():
    assert _normalize_url("") == ""


# ── _title_similarity ─────────────────────────────────────────────────────────


def test_title_similarity_identical():
    assert _title_similarity("Oil prices surge", "Oil prices surge") == 1.0


def test_title_similarity_high():
    r = _title_similarity("Oil prices surge in Asia", "Oil prices surge across Asia")
    assert r >= 0.8


def test_title_similarity_low():
    r = _title_similarity("Oil prices surge", "New electric car record")
    assert r < 0.5


def test_title_similarity_empty():
    assert _title_similarity("", "anything") == 0.0
    assert _title_similarity("anything", "") == 0.0


# ── _is_duplicate ────────────────────────────────────────────────────────────


def _article(**kwargs) -> Article:
    defaults: Article = {
        "url": "https://example.com/article",
        "title": "Oil prices surge",
        "title_kr": "유가 급등",
        "score": 20.0,
        "scope": "local",
        "country": "KR",
        "sector": "윤활유동향",
    }
    defaults.update(kwargs)
    return defaults


def test_is_duplicate_by_url():
    seen_urls: set[str] = {"https://example.com/article"}
    seen_titles: list[str] = []
    a = _article(url="https://example.com/article?utm_source=x")
    assert _is_duplicate(a, seen_urls, seen_titles)


def test_is_duplicate_by_title_similarity():
    seen_urls: set[str] = set()
    seen_titles = ["Oil prices surge across Asia markets"]
    a = _article(url="https://other.com/news", title_kr="Oil prices surge across Asian markets")
    assert _is_duplicate(a, seen_urls, seen_titles)


def test_not_duplicate_different_article():
    seen_urls: set[str] = {"https://example.com/article"}
    seen_titles = ["Oil prices surge"]
    a = _article(url="https://other.com/news", title_kr="Electric vehicles new record")
    assert not _is_duplicate(a, seen_urls, seen_titles)


# ── build_unified_issue ───────────────────────────────────────────────────────


def _make_articles(country: str, scope: str, count: int, base_score: float = 15.0) -> list[Article]:
    return [
        _article(
            url=f"https://example.com/{country.lower()}-{scope}-{i}",
            title=f"{country} {scope} article {i}",
            title_kr=f"{country} {scope} 기사 {i}",
            scope=scope,
            country=country,
            score=base_score - i,
        )
        for i in range(count)
    ]


def test_global_articles_deduped_across_countries():
    """Same global article appearing in multiple countries' lists → kept once."""
    shared = _article(
        url="https://news.com/global-oil",
        title_kr="글로벌 유가 동향",
        scope="global",
        country="KR",
        score=25.0,
    )
    grouped = {
        "KR": [shared],
        "RU": [dict(shared, country="RU")],  # same URL, different country key
    }
    issue = build_unified_issue(
        run_id="test",
        date_str="20260811",
        countries=["KR", "RU"],
        grouped_articles=grouped,
        insights_by_country={},
        recommendations_by_country={},
        kpi_data={},
    )
    assert len(issue["global_section"]["articles"]) == 1
    assert issue["global_section"]["articles"][0]["countries"] == ["GLOBAL"]


def test_global_articles_not_in_country_sections():
    """Article classified as global must not appear in any country section."""
    global_art = _article(
        url="https://news.com/global", title_kr="글로벌 원자재 가격 급등",
        scope="global", country="KR", score=20.0,
    )
    local_art = _article(
        url="https://kr.news.com/local", title_kr="한국 윤활유 수요 증가",
        scope="local", country="KR", score=15.0,
    )
    grouped = {"KR": [global_art, local_art], "RU": []}

    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR", "RU"],
        grouped_articles=grouped,
        insights_by_country={}, recommendations_by_country={}, kpi_data={},
    )

    kr_urls = [a["url"] for a in issue["country_sections"]["KR"]["articles"]]
    assert global_art["url"] not in kr_urls
    assert local_art["url"] in kr_urls


def test_country_section_exists_for_zero_article_country():
    """Country with no articles still gets a CountrySection (empty state UI)."""
    grouped = {"KR": _make_articles("KR", "local", 3), "RU": []}
    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR", "RU"],
        grouped_articles=grouped,
        insights_by_country={}, recommendations_by_country={}, kpi_data={},
    )
    assert "RU" in issue["country_sections"]
    assert issue["country_sections"]["RU"]["articles"] == []


def test_insights_and_recommendations_attached():
    """Writer-generated insights/recs are passed through into CountrySection."""
    grouped = {"KR": _make_articles("KR", "local", 2)}
    insights = {"KR": ["insight 1", "insight 2"]}
    recs = {"KR": ["rec 1"]}
    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR"],
        grouped_articles=grouped,
        insights_by_country=insights, recommendations_by_country=recs, kpi_data={},
    )
    assert issue["country_sections"]["KR"]["insights"] == ["insight 1", "insight 2"]
    assert issue["country_sections"]["KR"]["recommendations"] == ["rec 1"]


def test_article_countries_annotated():
    """Local articles should have countries=[country_code] annotated."""
    grouped = {"KR": _make_articles("KR", "local", 1)}
    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR"],
        grouped_articles=grouped,
        insights_by_country={}, recommendations_by_country={}, kpi_data={},
    )
    assert issue["country_sections"]["KR"]["articles"][0]["countries"] == ["KR"]


def test_other_country_scope_excluded():
    """Articles with scope='other_country' must be skipped entirely."""
    other = _article(url="https://x.com/other", scope="other_country", country="KR")
    grouped = {"KR": [other]}
    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR"],
        grouped_articles=grouped,
        insights_by_country={}, recommendations_by_country={}, kpi_data={},
    )
    assert issue["country_sections"]["KR"]["articles"] == []
    assert issue["global_section"]["articles"] == []


def test_global_section_sorted_by_score():
    """Higher-score global articles should appear first in GlobalSection."""
    arts = [
        _article(url=f"https://news.com/g{i}", scope="global", country="KR",
                 title_kr=f"글로벌 기사 {i}", score=float(i))
        for i in range(5)
    ]
    grouped = {"KR": arts}
    issue = build_unified_issue(
        run_id="test", date_str="20260811", countries=["KR"],
        grouped_articles=grouped,
        insights_by_country={}, recommendations_by_country={}, kpi_data={},
    )
    scores = [a["score"] for a in issue["global_section"]["articles"]]
    assert scores == sorted(scores, reverse=True)


# ── get_recipient_default_country ─────────────────────────────────────────────


def test_default_country_recipient_in_list():
    assert get_recipient_default_country("RU", ["KR", "RU", "VN"]) == "RU"


def test_default_country_fallback_to_kr():
    # recipient country not in available list
    assert get_recipient_default_country("XX", ["KR", "RU"]) == "KR"


def test_default_country_null_recipient():
    assert get_recipient_default_country(None, ["KR", "RU"]) == "KR"


def test_default_country_kr_not_in_list_uses_first():
    # KR not in list, fallback should use first country
    assert get_recipient_default_country(None, ["VN", "TH"]) == "VN"
