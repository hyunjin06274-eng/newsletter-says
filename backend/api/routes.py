"""FastAPI route definitions."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import (
    RunCreate, RunStatus, RunListResponse, RunListItem,
    ScheduleSettings, SettingsResponse, NewsletterPreview,
)
from backend.core.config import settings
from backend.core.database import Run, ScheduleConfig, get_session

router = APIRouter(prefix="/api")

# In-memory event queues for SSE (run_id -> list of events)
_event_queues: dict[str, asyncio.Queue] = {}
# In-memory run status cache
_active_runs: dict[str, dict] = {}


async def run_pipeline(run_id: str, countries: list[str], date_str: str, days: int, dry_run: bool):
    """Execute the LangGraph pipeline in background."""
    from backend.agent.graph import compile_graph, create_initial_state

    graph = compile_graph()
    initial_state = create_initial_state(countries=countries, date_str=date_str, days=days)
    initial_state["run_id"] = run_id

    queue = _event_queues.get(run_id)

    try:
        config = {"configurable": {"thread_id": run_id}}
        _active_runs[run_id] = {"status": "running", "phase": "keywords"}

        async for event in graph.astream(initial_state, config=config):
            # Extract phase updates from events
            for node_name, node_output in event.items():
                phase = node_output.get("current_phase", "")
                events = node_output.get("events", [])

                _active_runs[run_id] = {
                    "status": "running",
                    "phase": phase,
                    "node": node_name,
                }

                if queue:
                    for e in events:
                        await queue.put(e)

        _active_runs[run_id] = {"status": "completed", "phase": "complete"}
        if queue:
            await queue.put({"type": "complete", "ts": datetime.now().isoformat()})

    except Exception as e:
        _active_runs[run_id] = {"status": "failed", "phase": "error", "error": str(e)}
        if queue:
            await queue.put({"type": "error", "ts": datetime.now().isoformat(), "error": str(e)})


@router.post("/runs", response_model=RunStatus)
async def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Start a new newsletter pipeline run."""
    run_id = str(uuid.uuid4())
    date_str = body.date_str or datetime.now().strftime("%Y%m%d")

    db_run = Run(
        id=run_id,
        countries=json.dumps(body.countries),
        date_str=date_str,
        status="running",
        current_phase="keywords",
    )
    session.add(db_run)
    await session.commit()

    _event_queues[run_id] = asyncio.Queue()

    background_tasks.add_task(
        run_pipeline, run_id, body.countries, date_str, body.days, body.dry_run
    )

    return RunStatus(
        id=run_id,
        countries=body.countries,
        date_str=date_str,
        status="running",
        current_phase="keywords",
        phase_status={},
        errors=[],
        audit_iterations=0,
        total_collected=0,
        total_filtered=0,
        total_sent=0,
        created_at=datetime.utcnow(),
        completed_at=None,
    )


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    """Get run status."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    db_run = result.scalar_one_or_none()
    if not db_run:
        raise HTTPException(404, "Run not found")

    # Merge with active status
    active = _active_runs.get(run_id, {})

    return RunStatus(
        id=db_run.id,
        countries=json.loads(db_run.countries),
        date_str=db_run.date_str,
        status=active.get("status", db_run.status),
        current_phase=active.get("phase", db_run.current_phase),
        phase_status=json.loads(db_run.phase_status),
        errors=json.loads(db_run.errors),
        audit_iterations=db_run.audit_iterations,
        total_collected=db_run.total_collected,
        total_filtered=db_run.total_filtered,
        total_sent=db_run.total_sent,
        created_at=db_run.created_at,
        completed_at=db_run.completed_at,
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
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List all runs with pagination."""
    total_result = await session.execute(select(func.count(Run.id)))
    total = total_result.scalar() or 0

    result = await session.execute(
        select(Run)
        .order_by(Run.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    runs = result.scalars().all()

    return RunListResponse(
        runs=[
            RunListItem(
                id=r.id,
                date_str=r.date_str,
                status=r.status,
                countries=json.loads(r.countries),
                total_sent=r.total_sent,
                created_at=r.created_at,
            )
            for r in runs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/newsletters/{run_id}")
async def get_newsletter(run_id: str, country: str = "KR", session: AsyncSession = Depends(get_session)):
    """Get generated newsletter HTML."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    db_run = result.scalar_one_or_none()
    if not db_run:
        raise HTTPException(404, "Run not found")

    newsletters = json.loads(db_run.newsletter_html or "{}")
    html = newsletters.get(country, "")
    if not html:
        raise HTTPException(404, f"Newsletter not found for {country}")

    return NewsletterPreview(
        country=country,
        html=html,
        date_str=db_run.date_str,
        article_count=0,
    )


@router.get("/settings")
async def get_settings(session: AsyncSession = Depends(get_session)):
    """Get current settings."""
    import os

    result = await session.execute(select(ScheduleConfig).order_by(ScheduleConfig.id.desc()).limit(1))
    config = result.scalar_one_or_none()

    schedule = ScheduleSettings()
    if config:
        schedule = ScheduleSettings(
            frequency=config.frequency,
            day_of_week=config.day_of_week,
            time=config.time,
            countries=json.loads(config.countries),
            is_active=config.is_active,
        )

    return SettingsResponse(
        schedule=schedule,
        api_keys_configured={
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "google": bool(os.environ.get("GOOGLE_API_KEY")),
            "tavily": bool(os.environ.get("TAVILY_API_KEY")),
        },
        gmail_authenticated=os.path.exists(settings.gmail_token_file),
    )


@router.put("/settings")
async def update_settings(body: ScheduleSettings, session: AsyncSession = Depends(get_session)):
    """Update schedule and recipient settings."""
    config = ScheduleConfig(
        frequency=body.frequency,
        day_of_week=body.day_of_week,
        time=body.time,
        countries=json.dumps(body.countries),
        is_active=body.is_active,
        updated_at=datetime.utcnow(),
    )
    session.add(config)
    await session.commit()

    return {"status": "ok", "message": "Settings updated"}
