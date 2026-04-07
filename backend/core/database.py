"""Supabase database client for settings, runs, and logs."""

import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qndliypxehqaveeuzwvg.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFuZGxpeXB4ZWhxYXZlZXV6d3ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1NTcxNjgsImV4cCI6MjA5MTEzMzE2OH0.5KHO_4hutG7liDcOUS6houRX5V2YYkdp1-3lkTKUA20")

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


async def init_db():
    """Verify Supabase connection on startup."""
    try:
        db = get_supabase()
        db.table("settings").select("id").limit(1).execute()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Supabase connection check: {e}")
