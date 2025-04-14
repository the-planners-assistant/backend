# app/services/constraints_service.py
import asyncio
import json
import asyncpg
import sys
from typing import List, Tuple, Dict, Any, Optional
from fastapi import Depends, HTTPException, status
import logging # Import logging

from app.models.schemas import LocationInput, ConstraintInfo
from app.db import get_db_connection

logger = logging.getLogger(__name__) # Get logger instance

# --- Async Service Function ---
async def get_constraints_for_location(
    location: LocationInput,
    radius: int = 500, # Default radius if needed for nearby queries
    conn: asyncpg.Connection = Depends(get_db_connection) # Dependency injection
) -> List[ConstraintInfo]:
    """
    Async service function to retrieve constraints intersecting a given location.
    Queries individual columns from the spatial_constraints table.
    """
    logger.info(f"Fetching constraints for Lat: {location.lat}, Lon: {location.lon}")
    logger.debug(f"Using database connection type: {type(conn)}") # Avoid logging connection object

    if not isinstance(conn, asyncpg.Connection):
         logger.error(f"Dependency injection failed: 'conn' is not an asyncpg.Connection, type {type(conn)}!")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Internal error: Database connection dependency failed."
         )

    affecting_results_raw: List[asyncpg.Record] = []
    # nearby_results_raw: List[asyncpg.Record] = [] # Uncomment if nearby query is used

    # Define columns to select - adapt based on actual table schema
    # Ensure 'name', 'constraint_type', 'documentation-url' exist or adjust selection
    select_columns = 'gid AS id, name, constraint_type, "documentation-url"'
    logger.debug(f"Selecting columns: {select_columns}")

    try:
        # --- Query for constraints that directly intersect the point ---
        intersect_query = f"""
            SELECT {select_columns}
            FROM spatial_constraints
            WHERE ST_Intersects(
                geom,
                ST_SetSRID(ST_MakePoint($1, $2), 4326)
            );
        """
        logger.debug(f"Executing intersect query with lon={location.lon}, lat={location.lat}")
        affecting_results_raw = await conn.fetch(
            intersect_query, location.lon, location.lat
        )
        logger.info(f"Intersect query returned {len(affecting_results_raw)} raw results.")

        # --- Optional: Query for constraints within the given radius ---
        # Uncomment and adapt if needed
        # nearby_query = f"""..."""
        # logger.debug(f"Executing nearby query with radius {radius}m...")
        # nearby_results_raw = await conn.fetch(...)
        # logger.info(f"Nearby query returned {len(nearby_results_raw)} raw results.")

    except asyncpg.PostgresError as db_err:
        # Log database specific errors
        error_code = db_err.sqlstate or "N/A"
        logger.error(f"Database query failed! Code: {error_code}, Message: {db_err}", exc_info=False) # No need for full traceback here usually
        hint = f" HINT: {db_err.hint}" if db_err.hint else ""
        detail_msg = f"Database query error: {db_err}{hint}"
        # Check for common errors
        if error_code == '42P01': # undefined_table
             detail_msg = "Database error: 'spatial_constraints' table not found."
             logger.error(detail_msg)
        elif error_code == '42703': # undefined_column
             detail_msg = "Database error: A required column (e.g., 'name', 'constraint_type', 'documentation-url') might be missing in 'spatial_constraints'."
             logger.error(detail_msg)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg
        )
    except Exception as e:
        # Log unexpected errors
        logger.exception("Unexpected error during constraint lookup.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during constraint lookup."
        )

    # --- Map DB results to Pydantic model ---
    constraints_list: List[ConstraintInfo] = []
    processed_ids = set()

    logger.debug(f"Mapping {len(affecting_results_raw)} affecting results to ConstraintInfo model...")
    for row in affecting_results_raw:
        row_dict = dict(row)
        item_id = row_dict.get('id')

        if item_id is None:
            logger.warning("Found DB row with missing 'id' (gid). Skipping.")
            continue
        if item_id in processed_ids:
            logger.debug(f"Skipping duplicate item ID: {item_id}")
            continue

        name = row_dict.get("name", "Unnamed Constraint")
        constraint_type = row_dict.get("constraint_type", "Unknown Type")
        doc_url = row_dict.get("documentation-url")
        explanation_available = bool(doc_url)

        logger.debug(f"Mapping Row ID {item_id}: Name='{name}', Type='{constraint_type}', HasDoc='{explanation_available}'")

        try:
            constraint_info = ConstraintInfo(
                id=str(item_id),
                name=str(name) if name is not None else "Unnamed Constraint",
                type=str(constraint_type) if constraint_type is not None else "Unknown Type",
                explanation_available=explanation_available
            )
            constraints_list.append(constraint_info)
            processed_ids.add(item_id)
        except Exception as model_err: # Catch potential Pydantic validation errors
            logger.error(f"Error creating ConstraintInfo model for ID {item_id}: {model_err}", exc_info=True)

    # --- Optional: Process nearby_results_raw similarly ---
    # logger.debug(f"Mapping {len(nearby_results_raw)} nearby results...")
    # ...

    logger.info(f"Successfully mapped {len(constraints_list)} constraints.")
    return constraints_list