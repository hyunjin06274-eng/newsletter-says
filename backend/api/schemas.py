"""Pydantic schemas for API request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class RunCreate(BaseModel):
    countries: list[str] = ["KR", "RU", "VN", "TH", "PH", "PK"]
    date_str: Optional[str] = None  # YYYYMMDD, defaults to today
    days: int = 30
    dry_run: bool = False


class RunStatus(BaseModel):
    id: str
    countries: list[str]
    date_str: str
    status: str
    current_phase: str
    phase_status: dict[str, str]
    errors: list[str]
    audit_iterations: int
    total_collected: int
    total_filtered: int
    total_sent: int
    created_at: datetime
    completed_at: Optional[datetime]


class RunListItem(BaseModel):
    id: str
    date_str: str
    status: str
    countries: list[str]
    total_sent: int
    created_at: datetime


class RunListResponse(BaseModel):
    runs: list[RunListItem]
    total: int
    page: int
    page_size: int


class CountryRecipients(BaseModel):
    country: str
    recipients: list[str]


class ScheduleSettings(BaseModel):
    frequency: str = "weekly"  # weekly, daily, monthly
    day_of_week: str = "Wednesday"
    time: str = "10:00"
    countries: list[str] = ["KR", "RU", "VN", "TH", "PH", "PK"]
    is_active: bool = True
    country_recipients: list[CountryRecipients] = []


class SettingsResponse(BaseModel):
    schedule: ScheduleSettings
    api_keys_configured: dict[str, bool]
    gmail_authenticated: bool


class NewsletterPreview(BaseModel):
    country: str
    html: str
    date_str: str
    article_count: int


class SSEEvent(BaseModel):
    type: str
    phase: Optional[str] = None
    ts: str
    data: Optional[dict] = None
