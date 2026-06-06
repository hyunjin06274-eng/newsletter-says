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


def should_continue_after_merge(state: NewsletterState) -> str:
    """Fail early if no articles were collected at all."""
    merged = state.get("merged_articles", {})
    total = sum(len(articles) for articles in merged.values())

    if total == 0:
        print("PIPELINE ABORT: No articles collected for any country. Check API keys and network.", flush=True)
        return "abort"

    return "continue"


def should_continue_after_score(state: NewsletterState) -> str:
    """Fail early if scoring produced zero usable articles (likely API key issue)."""
    scored = state.get("scored_articles", {})
    total = sum(len(articles) for articles in scored.values())

    if total == 0:
        print("PIPELINE ABORT: 0 articles passed scoring for all countries. Likely cause: Anthropic API credit exhausted or API key invalid.", flush=True)
        return "abort"

    # Warn if very few articles passed
    countries_with_articles = sum(1 for articles in scored.values() if len(articles) > 0)
    total_countries = len(scored)
    if countries_with_articles < total_countries:
        empty = [c for c, a in scored.items() if len(a) == 0]
        print(f"PIPELINE WARNING: {len(empty)} countries have 0 scored articles: {empty}", flush=True)

    return "continue"


async def abort_pipeline(state: NewsletterState) -> dict:
    """Abort node: mark pipeline as failed with clear error message."""
    from datetime import datetime

    errors = state.get("errors", [])

    # Detect the specific failure reason
    scored = state.get("scored_articles", {})
    merged = state.get("merged_articles", {})
    total_scored = sum(len(a) for a in scored.values())
    total_merged = sum(len(a) for a in merged.values())

    if total_merged == 0:
        reason = "No articles collected. Check Tavily API key and network connectivity."
    elif total_scored == 0:
        reason = "All articles scored 0. Anthropic API credit is likely exhausted. Please top up at console.anthropic.com."
    else:
        reason = "Pipeline aborted due to insufficient data."

    errors.append(f"PIPELINE FAILED: {reason}")
    print(f"PIPELINE FAILED: {reason}", flush=True)

    return {
        "current_phase": "failed",
        "phase_status": {**state.get("phase_status", {}), "pipeline": "failed"},
        "errors": errors,
        "events": state.get("events", []) + [
            {"type": "error", "message": reason, "ts": datetime.now().isoformat()}
        ],
    }


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
    builder.add_node("abort", abort_pipeline)

    # Linear flow with failure checkpoints
    builder.add_edge("generate_keywords", "collect")
    builder.add_edge("collect", "merge")

    # Checkpoint 1: after merge, check if any articles were collected
    builder.add_conditional_edges(
        "merge",
        should_continue_after_merge,
        {
            "continue": "score",
            "abort": "abort",
        },
    )

    # Checkpoint 2: after score, check if any articles passed scoring
    builder.add_conditional_edges(
        "score",
        should_continue_after_score,
        {
            "continue": "enrich",
            "abort": "abort",
        },
    )

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
    builder.add_edge("abort", END)

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
