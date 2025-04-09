# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Define the path to the .env file relative to this config file's location
# This assumes .env is in the 'backend' directory, one level up from 'app/core'
env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    # Example setting - replace with actual config needed (e.g., DB URL, API Keys)
    PROJECT_NAME: str = "The Planner's Assistant API"
    API_V1_STR: str = "/api/v1" # Example for API versioning prefix

    # Example Database URL (replace with your actual connection string)
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@host:port/db"
    DATABASE_URL: str | None = None # Make optional if DB is not setup yet

    # Redis URL for Celery Broker/Backend
    REDIS_URL: str = "redis://localhost:6379/0" # Load from .env

    # Add other settings here (e.g., AI model paths, external API keys)

    # Load settings from .env file
    model_config = SettingsConfigDict(env_file=str(env_path), extra='ignore')

# Create a single instance of the settings to be imported elsewhere
settings = Settings()