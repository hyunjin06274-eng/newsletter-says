"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    google_api_key: str = ""
    tavily_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./newsletter.db"

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Gmail
    gmail_sender: str = "skenbizst@gmail.com"
    gmail_credentials_file: str = ".gmail_credentials.json"
    gmail_token_file: str = ".gmail_token.json"

    # Pipeline defaults
    default_countries: list[str] = ["KR", "RU", "VN", "TH", "PH", "PK"]
    default_days: int = 30
    max_audit_iterations: int = 3
    default_schedule_day: str = "Tuesday"
    default_schedule_time: str = "08:00"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
