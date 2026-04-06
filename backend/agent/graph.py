"""
LangGraph workflow for the self-correcting newsletter pipeline.

Flow:
  generate_keywords -> collect -> merge -> score -> enrich -> group -> write -> audit
                                                                         ^         |
                                                                         | (fail)  |
                                                                         +---------+
                                                                         (pass) -> send
"""

from __future__ import annotations

import uuid
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.state import NewsletterState, PHASE_NAMES
from backend.agent.nodes.keyword_generator import generate_keywords
from backend.agent.nodes.collector import collect_news
from backend.agent.nodes.merger import merge_and_dedupe
from backend.agent.nodes.scorer import score_articles
from backend.agent.nodes.enricher import enrich_snippets
from backend.agent.nodes.grouper import group_articles
from backend.agent.nodes.writer import write_newsletter
from backend.agent.nodes.auditor import audit_newsletter
from backend.agent.nodes.sender import send_newsletter


def should_retry_or_send(state: NewsletterState) -> str:
    """Conditional edge: retry writing if audit failed, otherwise send."""
    feedback = state.get("audit_feedback", {})
    iteration = state.get("audit_iteration", 0)
    max_iter = state.get("max_audit_iterations", 3)

    # Check if all countries passed
    all_passed = all(fb.get("passed", False) for fb in feedback.values())

    if all_passed:
        return "send"

    if iteration >= max_iter:
        # Force send with warning after max iterations
        return "send"

    return "rewrite"


def create_graph() -> StateGraph:
    """Build and return the newsletter pipeline graph."""
    builder = StateGraph(NewsletterState)

    # Add nodes
    builder.add_node("generate_keywords", generate_keywords)
    builder.add_node("collect", collect_news)
    builder.add_node("merge", merge_and_dedupe)
    builder.add_node("score", score_articles)
    builder.add_node("enrich", enrich_snippets)
    builder.add_node("group", group_articles)
    builder.add_node("write", write_newsletter)
    builder.add_node("audit", audit_newsletter)
    builder.add_node("send", send_newsletter)

    # Linear flow
    builder.add_edge("generate_keywords", "collect")
    builder.add_edge("collect", "merge")
    builder.add_edge("merge", "score")
    builder.add_edge("score", "enrich")
    builder.add_edge("enrich", "group")
    builder.add_edge("group", "write")
    builder.add_edge("write", "audit")

    # Conditional: audit -> send or audit -> rewrite
    builder.add_conditional_edges(
        "audit",
        should_retry_or_send,
        {
            "send": "send",
            "rewrite": "write",
        },
    )

    builder.add_edge("send", END)

    # Entry point
    builder.set_entry_point("generate_keywords")

    return builder


def compile_graph():
    """Compile the graph with memory checkpointing."""
    builder = create_graph()
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


def create_initial_state(
    countries: list[str] | None = None,
    date_str: str | None = None,
    days: int = 30,
) -> NewsletterState:
    """Create initial state for a new run."""
    if countries is None:
        countries = ["KR", "RU", "VN", "TH", "PH", "PK"]
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    return NewsletterState(
        run_id=str(uuid.uuid4()),
        countries=countries,
        date_str=date_str,
        days=days,
        current_phase="keywords",
        phase_status={name: "pending" for name in PHASE_NAMES},
        errors=[],
        keywords={},
        raw_articles={},
        merged_articles={},
        scored_articles={},
        enriched_articles={},
        grouped_articles={},
        newsletters={},
        audit_iteration=0,
        max_audit_iterations=3,
        audit_feedback={},
        send_results={},
        events=[],
    )
