# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Optional

# Define the path to the .env file relative to this config file's location
# Assumes .env is in the 'backend' directory
env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "The Planner's Assistant API"
    API_V1_STR: str = "/api/v1"

    # --- Database Configuration ---
    # *** Changed field names to match standard PG env vars used in .env ***
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGDATABASE: str = "mydatabase" # Default if not in .env
    PGUSER: str = "postgres"     # Default if not in .env
    PGPASSWORD: str = "password"   # Default if not in .env
    PGSCHEMA: str = "public"     # Default if not in .env

    # --- Redis Configuration ---
    REDIS_URL: str = "redis://localhost:6379/0" # Load from .env

    # --- Other Settings ---
    # Add other settings here

    # Load settings from .env file
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        extra='ignore',
        # Optional: Add case_sensitive=False if needed, but matching case is safer
        # case_sensitive=False
    )

# Create a single instance of the settings to be imported elsewhere
settings = Settings()

# Example: Accessing a setting elsewhere in your code
# from app.core.config import settings
# db_host = settings.PGHOST
# print(f"Database host from settings: {db_host}")