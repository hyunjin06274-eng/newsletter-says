"""LangGraph State definitions for the newsletter pipeline."""

from __future__ import annotations

from typing import TypedDict, Literal
from dataclasses import dataclass, field


class Article(TypedDict, total=False):
    url: str
    title: str
    snippet: str
    summary_kr: str
    source: str
    published_date: str
    collection_domain: str
    score: float
    tags: list[str]
    country: str
    group_id: str | None


class AuditFeedback(TypedDict):
    passed: bool
    score: float
    issues: list[str]
    suggestions: list[str]


class NewsletterState(TypedDict, total=False):
    """Main state flowing through the LangGraph pipeline."""

    # Run configuration
    run_id: str
    countries: list[str]
    date_str: str
    days: int

    # Phase tracking
    current_phase: str
    phase_status: dict[str, str]  # phase_name -> "pending"|"running"|"done"|"failed"
    errors: list[str]

    # Phase 0.5: Keywords
    keywords: dict[str, list[str]]  # country -> keywords

    # Phase 1: Collection
    raw_articles: dict[str, list[Article]]  # country -> articles

    # Phase 1.5: Merged
    merged_articles: dict[str, list[Article]]

    # Phase 2: Scored
    scored_articles: dict[str, list[Article]]

    # Phase 2.5: Enriched
    enriched_articles: dict[str, list[Article]]

    # Phase 2.7: Grouped
    grouped_articles: dict[str, list[Article]]

    # Phase 3: Newsletter HTML
    newsletters: dict[str, str]  # country -> html

    # Phase 3.5: Audit
    audit_iteration: int
    max_audit_iterations: int
    audit_feedback: dict[str, AuditFeedback]  # country -> feedback

    # Phase 4: Sending
    send_results: dict[str, bool]  # country -> success

    # SSE events
    events: list[dict]


# Node status constants
PHASE_NAMES = [
    "keywords",
    "collection",
    "merge",
    "scoring",
    "enrichment",
    "grouping",
    "writing",
    "auditing",
    "sending",
]
