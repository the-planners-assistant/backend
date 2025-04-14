# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Optional
import logging

env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "The Planner's Assistant API"
    API_V1_STR: str = "/api/v1"

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Google Cloud APIs ---
    GOOGLE_GEOCODE_API_KEY: Optional[str] = None
    # Add key for Maps Static/Street View (can often be same as Geocode key if APIs enabled)
    MAPS_STATIC_API_KEY: Optional[str] = None 

    # --- Database Configuration ---
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGDATABASE: str = "mydatabase"
    PGUSER: str = "postgres"
    PGPASSWORD: str = "password"
    PGSCHEMA: str = "public"

    # --- Redis Configuration ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- LLM Configuration ---
    GEMINI_API_KEY: Optional[str] = None
    RERANKING_LLM_MODEL_NAME: str = "gemini-2.0-flash"
    REPORTING_LLM_MODEL_NAME: str = "gemini-2.5-pro-preview-03-25"

    # --- Other Settings ---

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

settings = Settings()

def get_log_level() -> int:
    level_str = settings.LOG_LEVEL.upper()
    return getattr(logging, level_str, logging.INFO)