"""FastAPI route definitions — Supabase backend."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import (
    RunCreate, RunStatus, RunListResponse, RunListItem,
    ScheduleSettings, SettingsResponse, NewsletterPreview,
)
from backend.core.config import settings
from backend.core.database import get_supabase

router = APIRouter(prefix="/api")

# In-memory event queues for SSE
_event_queues: dict[str, asyncio.Queue] = {}
_active_runs: dict[str, dict] = {}


async def run_pipeline(run_id: str, countries: list[str], date_str: str, days: int, dry_run: bool):
    """Execute the LangGraph pipeline in background."""
    import traceback
    from backend.agent.graph import compile_graph, create_initial_state

    graph = compile_graph()
    initial_state = create_initial_state(countries=countries, date_str=date_str, days=days)
    initial_state["run_id"] = run_id
    initial_state["max_audit_iterations"] = 3

    queue = _event_queues.get(run_id)
    final_state = {}
    db = get_supabase()

    try:
        config = {"configurable": {"thread_id": run_id}}
        _active_runs[run_id] = {"status": "running", "phase": "keywords"}

        async for event in graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                phase = node_output.get("current_phase", "")
                final_state.update(node_output)
                _active_runs[run_id] = {"status": "running", "phase": phase, "node": node_name}

                # Log to Supabase
                try:
                    db.table("run_logs").insert({
                        "run_id": run_id, "phase": phase, "level": "info",
                        "message": f"Node {node_name} completed",
                    }).execute()
                except Exception:
                    pass

                if queue:
                    for e in node_output.get("events", []):
                        await queue.put(e)

        _active_runs[run_id] = {"status": "completed", "phase": "complete"}

        # Save results to Supabase
        try:
            raw = final_state.get("raw_articles", {})
            scored = final_state.get("scored_articles", {})
            db.table("runs").update({
                "status": "completed",
                "current_phase": "complete",
                "completed_at": datetime.utcnow().isoformat(),
                "newsletter_html": final_state.get("newsletters", {}),
                "audit_iterations": final_state.get("audit_iteration", 0),
                "total_collected": sum(len(v) for v in raw.values()),
                "total_filtered": sum(len(v) for v in scored.values()),
                "total_sent": sum(1 for v in final_state.get("send_results", {}).values() if v),
            }).eq("id", run_id).execute()
        except Exception as e:
            logging.getLogger(__name__).error(f"DB update failed: {e}")

        if queue:
            await queue.put({"type": "complete", "ts": datetime.now().isoformat()})

    except Exception as e:
        logging.getLogger(__name__).error(f"Pipeline failed: {traceback.format_exc()}")
        _active_runs[run_id] = {"status": "failed", "phase": "error", "error": str(e)}
        try:
            db.table("runs").update({
                "status": "failed", "errors": [str(e)],
            }).eq("id", run_id).execute()
            db.table("run_logs").insert({
                "run_id": run_id, "phase": "error", "level": "error",
                "message": str(e),
            }).execute()
        except Exception:
            pass
        if queue:
            await queue.put({"type": "error", "ts": datetime.now().isoformat(), "error": str(e)})


@router.post("/runs", response_model=RunStatus)
async def create_run(body: RunCreate, background_tasks: BackgroundTasks):
    """Start a new newsletter pipeline run."""
    run_id = str(uuid.uuid4())
    date_str = body.date_str or datetime.now().strftime("%Y%m%d")
    db = get_supabase()

    db.table("runs").insert({
        "id": run_id,
        "countries": body.countries,
        "date_str": date_str,
        "status": "running",
        "current_phase": "keywords",
    }).execute()

    _event_queues[run_id] = asyncio.Queue()

    background_tasks.add_task(
        run_pipeline, run_id, body.countries, date_str, body.days, body.dry_run
    )

    return RunStatus(
        id=run_id, countries=body.countries, date_str=date_str,
        status="running", current_phase="keywords", phase_status={},
        errors=[], audit_iterations=0,
        total_collected=0, total_filtered=0, total_sent=0,
        created_at=datetime.utcnow(), completed_at=None,
    )


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run(run_id: str):
    """Get run status."""
    db = get_supabase()
    result = db.table("runs").select("*").eq("id", run_id).execute()
    if not result.data:
        raise HTTPException(404, "Run not found")

    r = result.data[0]
    active = _active_runs.get(run_id, {})

    return RunStatus(
        id=r["id"],
        countries=r.get("countries", []),
        date_str=r.get("date_str", ""),
        status=active.get("status", r.get("status", "pending")),
        current_phase=active.get("phase", r.get("current_phase", "")),
        phase_status=r.get("phase_status", {}),
        errors=r.get("errors", []),
        audit_iterations=r.get("audit_iterations", 0),
        total_collected=r.get("total_collected", 0),
        total_filtered=r.get("total_filtered", 0),
        total_sent=r.get("total_sent", 0),
        created_at=r.get("created_at", datetime.utcnow().isoformat()),
        completed_at=r.get("completed_at"),
    )


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: str):
    """SSE stream for real-time run updates."""
    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()
    queue = _event_queues[run_id]

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"event": event.get("type", "update"), "data": json.dumps(event)}
                if event.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


@router.get("/runs")
async def list_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """List all runs with pagination."""
    db = get_supabase()
    offset = (page - 1) * page_size

    result = db.table("runs").select("*", count="exact") \
        .order("created_at", desc=True) \
        .range(offset, offset + page_size - 1) \
        .execute()

    total = result.count or 0

    return RunListResponse(
        runs=[
            RunListItem(
                id=r["id"], date_str=r.get("date_str", ""),
                status=_active_runs.get(r["id"], {}).get("status", r.get("status", "pending")),
                countries=r.get("countries", []),
                total_sent=r.get("total_sent", 0),
                created_at=r.get("created_at", ""),
            )
            for r in result.data
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/newsletters/{run_id}")
async def get_newsletter(run_id: str, country: str = "KR"):
    """Get generated newsletter HTML."""
    db = get_supabase()
    result = db.table("runs").select("newsletter_html,date_str").eq("id", run_id).execute()
    if not result.data:
        raise HTTPException(404, "Run not found")

    newsletters = result.data[0].get("newsletter_html", {})
    html = newsletters.get(country, "")
    if not html:
        raise HTTPException(404, f"Newsletter not found for {country}")

    return NewsletterPreview(
        country=country, html=html,
        date_str=result.data[0].get("date_str", ""), article_count=0,
    )


@router.get("/settings")
async def get_settings():
    """Get current settings."""
    import os
    db = get_supabase()

    result = db.table("settings").select("*").order("id", desc=True).limit(1).execute()

    schedule = ScheduleSettings()
    if result.data:
        config = result.data[0]
        recipients = config.get("country_recipients", [])
        schedule = ScheduleSettings(
            frequency=config.get("frequency", "weekly"),
            day_of_week=config.get("day_of_week", "Tuesday"),
            time=config.get("time", "09:00"),
            countries=config.get("countries", ["KR", "RU", "VN", "TH", "PH", "PK"]),
            is_active=config.get("is_active", True),
            country_recipients=[
                {"country": r["country"], "recipients": r["recipients"]}
                for r in recipients if isinstance(r, dict)
            ],
        )

    return SettingsResponse(
        schedule=schedule,
        api_keys_configured={
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "google": bool(os.environ.get("GOOGLE_API_KEY")),
            "tavily": bool(os.environ.get("TAVILY_API_KEY")),
        },
        gmail_authenticated=bool(os.environ.get("GMAIL_TOKEN_JSON")),
    )


@router.put("/settings")
async def update_settings(body: ScheduleSettings):
    """Update schedule and recipient settings."""
    db = get_supabase()

    recipients_list = [
        {"country": cr.country, "recipients": cr.recipients}
        for cr in body.country_recipients
    ] if body.country_recipients else []

    db.table("settings").insert({
        "frequency": body.frequency,
        "day_of_week": body.day_of_week,
        "time": body.time,
        "countries": body.countries,
        "is_active": body.is_active,
        "country_recipients": recipients_list,
        "updated_at": datetime.utcnow().isoformat(),
    }).execute()

    return {"status": "ok", "message": "Settings saved"}


@router.get("/logs/{run_id}")
async def get_run_logs(run_id: str):
    """Get detailed logs for a run."""
    db = get_supabase()
    result = db.table("run_logs").select("*").eq("run_id", run_id) \
        .order("created_at", desc=False).execute()
    return {"logs": result.data}
