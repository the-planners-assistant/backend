# app/services/constraints_service.py
import asyncio
import json
import asyncpg # Use asyncpg
import sys # Import sys
from typing import List, Tuple, Dict, Any, Optional # Added Optional
from fastapi import Depends, HTTPException, status

# Assuming these imports are correct relative to your project structure
from app.models.schemas import LocationInput, ConstraintInfo
# Import the dependency function (adjust path as needed)
from app.db import get_db_connection

# --- Async Service Function ---
async def get_constraints_for_location(
    location: LocationInput,
    radius: int = 500,
    conn: asyncpg.Connection = Depends(get_db_connection)
) -> List[ConstraintInfo]:
    """
    Async service function to retrieve constraints intersecting a given location.
    Queries individual columns (gid, name, constraint_type, etc.) from the
    spatial_constraints table.
    """
    print(f"SERVICE ASYNC: Fetching constraints for Lat: {location.lat}, Lon: {location.lon}")
    print(f"SERVICE ASYNC DEBUG: Type of 'conn' object is: {type(conn)}")

    if not isinstance(conn, asyncpg.Connection):
         print(f"SERVICE ASYNC ERROR: 'conn' is not an asyncpg.Connection, type {type(conn)}!")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Internal error: Database connection dependency failed."
         )

    affecting_results_raw: List[asyncpg.Record] = []
    nearby_results_raw: List[asyncpg.Record] = []

    # Define columns to select - adapt based on actual columns created by ogr2ogr
    # and what might be needed for display or logic.
    # Common ones likely available from properties + constraint_type added by loader.
    # Use quotes for names with hyphens or special characters.
    select_columns = 'gid AS id, name, constraint_type, "documentation-url"'

    try:
        # --- Query for constraints that directly intersect the point ---
        # *** MODIFIED: Select individual columns ***
        intersect_query = f"""
            SELECT {select_columns}
            FROM spatial_constraints
            WHERE ST_Intersects(
                geom,
                ST_SetSRID(ST_MakePoint($1, $2), 4326)
            );
        """
        affecting_results_raw = await conn.fetch(
            intersect_query, location.lon, location.lat
        )

        # --- Query for constraints within the given radius ---
        # *** MODIFIED: Select individual columns ***
        # Note: You might want different columns or logic for nearby results
        nearby_query = f"""
            SELECT {select_columns},
                   ST_Distance(
                       geom::geography,
                       ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                   ) AS distance_m
            FROM spatial_constraints
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography,
                $5 -- radius in meters
            )
            ORDER BY distance_m;
        """
        nearby_results_raw = await conn.fetch(
            nearby_query,
            location.lon, location.lat, # For ST_Distance point
            location.lon, location.lat, # For ST_DWithin center point
            float(radius) # For ST_DWithin radius
        )

    except asyncpg.PostgresError as e:
        error_code = e.sqlstate or "N/A"
        print(f"SERVICE DB ERROR: Database query failed (Code: {error_code}): {e}", file=sys.stderr)
        hint = f" HINT: {e.hint}" if e.hint else ""
        # Check for common missing column error (if ogr2ogr didn't create expected cols)
        if error_code == '42703': # undefined_column
             print("Hint: A required column (like 'name', 'constraint_type', 'documentation-url') might be missing from the spatial_constraints table for some loaded datasets.", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query error: {e}{hint}"
        )
    except Exception as e:
        print(f"SERVICE UNEXPECTED ERROR: Error during constraint lookup ({type(e).__name__}): {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during constraint lookup."
        )

    # --- Map DB results to Pydantic model ---
    constraints_list: List[ConstraintInfo] = []
    processed_ids = set() # Keep track of processed GIDs

    print(f"DEBUG: Processing {len(affecting_results_raw)} affecting results...")
    for row in affecting_results_raw:
        # Convert record to dictionary for easier access (.get with default)
        row_dict = dict(row)

        item_id = row_dict.get('id') # Should exist ('gid' AS 'id')
        if item_id is None:
            print("Warning: Found row with missing ID (gid). Skipping.", file=sys.stderr)
            continue # Skip if gid is somehow missing

        if item_id in processed_ids:
            continue # Skip duplicates if query returns multiple

        # *** MODIFIED: Get values directly from row dict ***
        name = row_dict.get("name", "Unnamed Constraint")
        # 'constraint_type' column was added and populated by the loader script's -sql
        constraint_type = row_dict.get("constraint_type", "Unknown Type")
        # Infer explanation_available based on presence of a documentation URL
        # Assumes 'documentation-url' column exists and was selected
        doc_url = row_dict.get("documentation-url")
        explanation_available = bool(doc_url) # True if doc_url is not None and not empty

        # *** REMOVED: No longer reading from 'properties' dict ***
        # props = row.get('properties') or {}
        # print(f"DEBUG: Row ID {item_id}, Properties: {props}", file=sys.stderr) # No longer needed

        print(f"DEBUG: Mapping Row ID {item_id}, Name: '{name}', Type: '{constraint_type}', DocURL: '{doc_url}' -> Explanation: {explanation_available}", file=sys.stderr)

        constraint_info = ConstraintInfo(
            id=str(item_id),
            name=str(name) if name is not None else "Unnamed Constraint",
            type=str(constraint_type) if constraint_type is not None else "Unknown Type",
            explanation_available=explanation_available
        )
        constraints_list.append(constraint_info)
        processed_ids.add(item_id)

    # --- Optional: Process nearby_results_raw similarly if needed ---
    # Make sure to check 'id' (aliased gid) against processed_ids to avoid duplicates
    # ...

    print(f"SERVICE ASYNC: Mapped {len(constraints_list)} constraints from DB query.")
    return constraints_list