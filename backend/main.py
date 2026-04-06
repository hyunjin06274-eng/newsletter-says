"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.api.routes import router
from backend.core.config import settings
from backend.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="SK Enmove Newsletter SaaS",
    description="Self-correcting MI newsletter pipeline with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>SK Enmove Newsletter SaaS API</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>"


@app.get("/health")
async def health():
    return {"status": "ok"}
