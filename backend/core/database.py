"""SQLite database for run history and settings."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    countries = Column(Text)  # JSON list
    date_str = Column(String(8))
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    current_phase = Column(String(30), default="")
    phase_status = Column(Text, default="{}")  # JSON dict
    errors = Column(Text, default="[]")  # JSON list
    newsletter_html = Column(Text, default="{}")  # JSON dict: country -> html
    audit_iterations = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Stats
    total_collected = Column(Integer, default=0)
    total_filtered = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)


class ScheduleConfig(Base):
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    frequency = Column(String(20), default="weekly")
    day_of_week = Column(String(20), default="Tuesday")
    time = Column(String(5), default="08:00")
    countries = Column(Text, default='["KR","RU","VN","TH","PH","PK"]')
    is_active = Column(Boolean, default=True)
    country_recipients = Column(Text, default="[]")  # JSON: [{"country":"KR","recipients":["a@b.com"]}]
    days = Column(Integer, default=30)
    updated_at = Column(DateTime, default=datetime.utcnow)


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with async_session() as session:
        yield session
