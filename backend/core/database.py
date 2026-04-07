"""Supabase database client via REST API (no supabase-py dependency)."""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qndliypxehqaveeuzwvg.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFuZGxpeXB4ZWhxYXZlZXV6d3ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1NTcxNjgsImV4cCI6MjA5MTEzMzE2OH0.5KHO_4hutG7liDcOUS6houRX5V2YYkdp1-3lkTKUA20")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


class SupabaseClient:
    """Lightweight Supabase REST API client."""

    def __init__(self):
        self.base = f"{SUPABASE_URL}/rest/v1"

    def select(self, table: str, params: dict | None = None) -> list[dict]:
        """SELECT rows from table."""
        try:
            url = f"{self.base}/{table}"
            r = requests.get(url, headers=HEADERS, params=params or {}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Supabase SELECT {table}: {e}")
            return []

    def insert(self, table: str, data: dict) -> dict | None:
        """INSERT a row."""
        try:
            url = f"{self.base}/{table}"
            r = requests.post(url, headers=HEADERS, json=data, timeout=10)
            r.raise_for_status()
            result = r.json()
            return result[0] if isinstance(result, list) and result else result
        except Exception as e:
            logger.warning(f"Supabase INSERT {table}: {e}")
            return None

    def update(self, table: str, data: dict, match: dict) -> dict | None:
        """UPDATE rows matching conditions."""
        try:
            url = f"{self.base}/{table}"
            params = {f"{k}": f"eq.{v}" for k, v in match.items()}
            r = requests.patch(url, headers=HEADERS, json=data, params=params, timeout=10)
            r.raise_for_status()
            result = r.json()
            return result[0] if isinstance(result, list) and result else result
        except Exception as e:
            logger.warning(f"Supabase UPDATE {table}: {e}")
            return None


_client: SupabaseClient | None = None


def get_supabase() -> SupabaseClient:
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client


async def init_db():
    """Verify Supabase connection on startup."""
    try:
        db = get_supabase()
        result = db.select("settings", {"select": "id", "limit": "1"})
        logger.info(f"Supabase connected: {len(result)} settings rows")
    except Exception as e:
        logger.warning(f"Supabase connection check: {e}")
