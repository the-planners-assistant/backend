# app/db.py
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from typing import AsyncGenerator, Optional
import logging # Import logging

# Assuming settings load DB details from .env or environment vars
from app.core.config import settings

logger = logging.getLogger(__name__) # Get logger instance

# Global variable to hold the pool
DB_POOL: Optional[asyncpg.Pool] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for FastAPI lifespan events to manage the DB pool."""
    global DB_POOL
    # --- Startup ---
    logger.info("Attempting to create database connection pool...")
    try:
        DB_POOL = await asyncpg.create_pool(
            user=settings.PGUSER,
            password=settings.PGPASSWORD,
            database=settings.PGDATABASE,
            host=settings.PGHOST,
            port=settings.PGPORT,
            min_size=1,
            max_size=10
        )
        # Optional: Test connection on startup
        async with DB_POOL.acquire() as conn:
            db_version = await conn.fetchval("SELECT version()")
            logger.debug(f"Database connection test successful. Version: {db_version}")

        logger.info(f"Database connection pool created successfully for {settings.PGUSER}@{settings.PGHOST}:{settings.PGPORT}/{settings.PGDATABASE}")
    except Exception as e:
        logger.critical(f"Could not connect to database pool: {e}", exc_info=True) # Use critical for startup failure
        DB_POOL = None # Ensure pool is None if creation failed

    yield # Application runs here

    # --- Shutdown ---
    if DB_POOL:
        logger.info("Closing database connection pool...")
        try:
            await DB_POOL.close()
            logger.info("Database connection pool closed successfully.")
        except Exception as e:
            logger.error(f"Error closing database connection pool: {e}", exc_info=True)
    else:
        logger.warning("Database pool was not initialized, skipping closure.")


# FastAPI Dependency to get a connection from the pool
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency that yields an asyncpg connection from the pool."""
    if not DB_POOL:
        logger.error("get_db_connection called but DB_POOL is not initialized!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool is not available."
        )

    connection: Optional[asyncpg.Connection] = None
    try:
        # Acquire a connection from the pool
        logger.debug("Acquiring connection from pool...")
        connection = await DB_POOL.acquire()
        logger.debug(f"Connection {id(connection)} acquired from pool.")
        yield connection # Provide the connection to the endpoint/service
    except Exception as e:
        logger.error(f"Failed to acquire connection from pool: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to acquire database connection."
        )
    finally:
        if connection:
            logger.debug(f"Releasing connection {id(connection)} back to pool.")
            try:
                await DB_POOL.release(connection)
                logger.debug(f"Connection {id(connection)} released successfully.")
            except Exception as e:
                 logger.error(f"Error releasing connection {id(connection)}: {e}", exc_info=True)