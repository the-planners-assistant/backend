# app/services/constraints_service.py
import asyncio
import json
import asyncpg
import sys
from typing import List, Tuple, Dict, Any, Optional
from fastapi import Depends, HTTPException, status
import logging
from pathlib import Path # To load prompt file

from app.models.schemas import LocationInput, ConstraintInfo
from app.db import get_db_connection
from app.llm_clients import get_llm_client # Import LLM client factory
from app.utils.geo_utils import reverse_geocode  # <-- IMPORT REVERSE GEOCODE

logger = logging.getLogger(__name__)

# --- Path to prompts directory ---
PROMPT_DIR = Path(__file__).parent.parent / "prompts"

# --- Helper to load prompt template ---
def load_prompt_template(template_name: str) -> str:
    """Loads a prompt template file."""
    filepath = PROMPT_DIR / template_name
    logger.debug(f"Attempting to load prompt template from: {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            template = f.read()
        logger.debug(f"Successfully loaded prompt template: {template_name}")
        return template
    except FileNotFoundError:
        logger.error(f"Prompt template file not found: {filepath}")
        raise FileNotFoundError(f"Prompt template '{template_name}' not found at {filepath}")
    except Exception as e:
        logger.exception(f"Error loading prompt template: {filepath}")
        raise


# --- Async Service Function ---
async def get_constraints_for_location(
    location: LocationInput,
    radius: int = 500,
    conn: asyncpg.Connection = Depends(get_db_connection)
) -> List[ConstraintInfo]:
    """
    Fetches constraints intersecting the given location, retrieves a formatted address via reverse geocoding,
    and then re-ranks the constraints using an LLM.
    """
    logger.info(f"Fetching and re-ranking constraints for Lat: {location.lat}, Lon: {location.lon}")

    # --- Get Formatted Address ---
    formatted_address = await reverse_geocode(location.lat, location.lon)
    logger.info(f"Formatted address from reverse geocode: {formatted_address}")

    # --- 1. Fetch initial constraints from DB ---
    initial_constraints: List[ConstraintInfo] = []
    try:
        # (Database query logic remains the same as previous version)
        logger.debug(f"Using database connection type: {type(conn)}")
        if not isinstance(conn, asyncpg.Connection):
             logger.error(f"Dependency injection failed: 'conn' is not an asyncpg.Connection, type {type(conn)}!")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail="Internal error: Database connection dependency failed."
             )

        select_columns = 'gid AS id, name, constraint_type, "documentation-url"'
        intersect_query = f"""
            SELECT {select_columns}
            FROM spatial_constraints
            WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326));
        """
        logger.debug(f"Executing intersect query with lon={location.lon}, lat={location.lat}")
        affecting_results_raw = await conn.fetch(intersect_query, location.lon, location.lat)
        logger.info(f"Intersect query returned {len(affecting_results_raw)} raw results.")

        processed_ids = set()
        for row in affecting_results_raw:
            row_dict = dict(row)
            item_id = row_dict.get('id')
            if item_id is None or item_id in processed_ids: continue
            name = row_dict.get("name", "Unnamed Constraint")
            constraint_type = row_dict.get("constraint_type", "Unknown Type")
            doc_url = row_dict.get("documentation-url")
            explanation_available = bool(doc_url)
            try:
                constraint_info = ConstraintInfo(
                    id=str(item_id), name=str(name), type=str(constraint_type), explanation_available=explanation_available
                )
                initial_constraints.append(constraint_info)
                processed_ids.add(item_id)
            except Exception as model_err:
                logger.error(f"Error creating ConstraintInfo model for ID {item_id}: {model_err}", exc_info=True)

        logger.info(f"Successfully fetched and mapped {len(initial_constraints)} initial constraints from DB.")

    except asyncpg.PostgresError as db_err:
        # (DB Error handling remains the same)
        error_code = db_err.sqlstate or "N/A"; hint = f" HINT: {db_err.hint}" if db_err.hint else ""
        logger.error(f"Database query failed! Code: {error_code}, Message: {db_err}", exc_info=False)
        detail_msg = f"Database query error: {db_err}{hint}"
        if error_code == '42P01': detail_msg = "Database error: 'spatial_constraints' table not found."
        elif error_code == '42703': detail_msg = "Database error: A required column might be missing."
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)
    except Exception as e:
        logger.exception("Unexpected error during initial constraint lookup.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching constraints.")

    # --- 2. Re-rank using LLM if constraints found ---
    if not initial_constraints:
        logger.info("No initial constraints found, skipping re-ranking.")
        return []

    try:
        logger.debug("Attempting to get re-ranking LLM client.")
        rerank_client = get_llm_client(client_type="reranking")

        # Load the prompt template
        prompt_template = load_prompt_template("rerank_constraints.txt")

        # Prepare context for the template, including the formatted address.
        prompt_context = {
            "latitude": location.lat,
            "longitude": location.lon,
            "formatted_address": formatted_address
        }

        # Prepare items for the client (list of dictionaries)
        items_to_rank = [c.model_dump() for c in initial_constraints]

        logger.info(f"Calling re-ranking LLM ({rerank_client.model_name}) for {len(items_to_rank)} constraints...")

        # Call the modified rerank_items method with the template
        ranked_items_data = await rerank_client.rerank_items(
            items=items_to_rank,
            prompt_template=prompt_template,
            prompt_context=prompt_context
            # Pass kwargs like temperature if needed: temperature=0.1
        )
        logger.info(f"Re-ranking LLM returned {len(ranked_items_data)} potentially relevant constraints.")

        # --- 3. Map re-ranked data back to ConstraintInfo list ---
        # ranked_items_data contains the re-ordered list of dicts based on LLM output
        # We need to ensure they are valid ConstraintInfo objects
        final_ranked_constraints: List[ConstraintInfo] = []
        original_items_map = {item.id: item for item in initial_constraints}
        processed_ids_rerank = set()

        for item_data in ranked_items_data:
            item_id = item_data.get("id") # Should exist if rerank_items worked correctly
            if item_id in original_items_map and item_id not in processed_ids_rerank:
                 # Re-use the original ConstraintInfo object to preserve exact data
                 final_ranked_constraints.append(original_items_map[item_id])
                 processed_ids_rerank.add(item_id)
            else:
                 logger.warning(f"Post-reranking mapping encountered unknown/duplicate ID: {item_id}")

        logger.info(f"Final ranked constraint count: {len(final_ranked_constraints)}.")
        return final_ranked_constraints

    except FileNotFoundError as fnf_err:
         logger.error(f"Cannot perform re-ranking: {fnf_err}")
         logger.warning("Returning constraints in original DB order due to missing prompt template.")
         return initial_constraints # Fallback: return original order
    except (ValueError, NotImplementedError) as config_err:
         logger.error(f"LLM client configuration error for re-ranking: {config_err}", exc_info=False)
         logger.warning("Falling back to original constraint order due to configuration error.")
         return initial_constraints
    except Exception as e:
         logger.exception("Unexpected error during constraint re-ranking.")
         logger.warning("Falling back to original constraint order due to unexpected error.")
         return initial_constraints