# app/db.py
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from typing import AsyncGenerator, Optional

# Assuming settings load DB details from .env or environment vars
from app.core.config import settings # Import the updated settings

# Global variable to hold the pool
DB_POOL: Optional[asyncpg.Pool] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for FastAPI lifespan events to manage the DB pool."""
    # --- Startup ---
    print("INFO:     Attempting to create database connection pool...")
    try:
        global DB_POOL
        DB_POOL = await asyncpg.create_pool(
            # *** Use the updated setting names from config.py ***
            user=settings.PGUSER,
            password=settings.PGPASSWORD,
            database=settings.PGDATABASE,
            host=settings.PGHOST,
            port=settings.PGPORT,
            # --- Optional Pool Settings ---
            min_size=1,  # Minimum number of connections in the pool
            max_size=10 # Maximum number of connections in the pool
            # You can add other asyncpg pool options here if needed
            # e.g., command_timeout=60
        )
        # Optional: Test connection on startup
        # async with DB_POOL.acquire() as conn:
        #    await conn.execute("SELECT 1")

        # *** Update print statement to use correct setting names ***
        print(f"INFO:     Database connection pool created successfully for {settings.PGUSER}@{settings.PGHOST}:{settings.PGPORT}/{settings.PGDATABASE}")
    except Exception as e:
        print(f"FATAL:    Could not connect to database: {e}")
        DB_POOL = None # Ensure pool is None if creation failed

    yield # Application runs here

    # --- Shutdown ---
    if DB_POOL:
        print("INFO:     Closing database connection pool...")
        # Use close() for graceful shutdown
        await DB_POOL.close()
        print("INFO:     Database connection pool closed.")

# FastAPI Dependency to get a connection from the pool
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency that yields an asyncpg connection from the pool."""
    if not DB_POOL:
        print("ERROR:    get_db_connection called but DB_POOL is not initialized!") # Debug print
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool is not available."
        )

    try:
        # Acquire a connection from the pool
        async with DB_POOL.acquire() as connection:
            print(f"DEBUG:    Connection {id(connection)} acquired from pool.") # Debug print
            # The connection is automatically released back to the pool
            # when the 'async with' block exits.
            yield connection # Provide the connection to the endpoint/service
            print(f"DEBUG:    Connection {id(connection)} released back to pool.") # Debug print
    except Exception as e:
        print(f"ERROR:    Failed to acquire connection from pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to acquire database connection."
        )