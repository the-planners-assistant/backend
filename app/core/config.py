# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Optional
import logging # For log level type hint

# Define the path to the .env file relative to this config file's location
# Assumes .env is in the 'backend' directory
env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "The Planner's Assistant API"
    API_V1_STR: str = "/api/v1"

    # --- Logging ---
    LOG_LEVEL: str = "INFO" # Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    # --- Database Configuration ---
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGDATABASE: str = "mydatabase" # Default if not in .env
    PGUSER: str = "postgres"     # Default if not in .env
    PGPASSWORD: str = "password"   # Default if not in .env
    PGSCHEMA: str = "public"     # Default if not in .env

    # --- Redis Configuration ---
    REDIS_URL: str = "redis://localhost:6379/0" # Load from .env

    # --- LLM Configuration ---
    GEMINI_API_KEY: Optional[str] = None

    # --- Re-ranking LLM ---
    RERANKING_LLM_MODEL_NAME: str = "gemini-2.0-flash"

    # --- Reporting LLM ---
    REPORTING_LLM_MODEL_NAME: str = "gemini-2.5-pro"

    # --- Other Settings ---
    # Add other settings here

    # Load settings from .env file
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False, # Allow overriding LOG_LEVEL with lowercase env var
    )

# Create a single instance of the settings to be imported elsewhere
settings = Settings()

# Helper function to get numeric log level
def get_log_level() -> int:
    level_str = settings.LOG_LEVEL.upper()
    return getattr(logging, level_str, logging.INFO)