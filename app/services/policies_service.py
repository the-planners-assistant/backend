# app/services/policies_service.py
import random
import asyncio
from typing import List
import logging

from app.models.schemas import LocationInput, PolicyInfo
from app.data.mock_data import MOCK_POLICIES # Import mock data
from app.llm_clients import get_llm_client
from app.utils.geo_utils import reverse_geocode # <-- IMPORT REVERSE GEOCODE
from app.services.constraints_service import load_prompt_template # Reuse prompt loader

logger = logging.getLogger(__name__)

# Assume a similar prompt template exists: app/prompts/rerank_policies.txt
# You'll need to create this file similar to rerank_constraints.txt

async def get_policies_for_location(location: LocationInput) -> List[PolicyInfo]:
    """
    Service function to retrieve/infer policies, get address, re-rank using LLM.
    Placeholder: Uses mock policies.
    """
    logger.info(f"Fetching policies for Lat: {location.lat}, Lon: {location.lon}")

    # --- Get Formatted Address ---
    formatted_address = await reverse_geocode(location.lat, location.lon) # <-- CALL GEOCODE
    logger.info(f"Formatted address from reverse geocode: {formatted_address}")

    # --- Fetch/Infer initial policies ---
    await asyncio.sleep(random.uniform(0.1, 0.3)) # Simulate work
    # Replace with actual logic (DB lookup or maybe an initial LLM call to infer relevant policy IDs)
    initial_policies_data = MOCK_POLICIES
    logger.debug("Using mock data for initial policies.")
    initial_policies_list = [
        PolicyInfo(id=p["id"], description=p["description"]) for p in initial_policies_data
    ]
    logger.info(f"Found/Inferred {len(initial_policies_list)} initial policies.")

    # --- Re-ranking Step ---
    if not initial_policies_list:
         logger.info("No initial policies found to re-rank.")
         return []

    try:
        logger.debug("Attempting to get re-ranking LLM client.")
        rerank_client = get_llm_client(client_type="reranking") # Could be same client as constraints

        # --- Load Policy Reranking Prompt ---
        # NOTE: Create 'rerank_policies.txt' in app/prompts/
        # It should be similar to rerank_constraints.txt but tailored for policies
        # and potentially using different context variables if needed.
        try:
             prompt_template = load_prompt_template("rerank_policies.txt") # ASSUMES THIS FILE EXISTS
        except FileNotFoundError:
             logger.error("Prompt template 'rerank_policies.txt' not found. Cannot re-rank policies.")
             return initial_policies_list # Fallback if prompt missing

        # Prepare context for the template
        prompt_context = {
            "latitude": location.lat,
            "longitude": location.lon,
            "formatted_address": formatted_address # <-- ADD ADDRESS TO CONTEXT
            # Add proposal text here if available and needed for policy ranking
        }

        items_to_rank = [p.model_dump() for p in initial_policies_list]
        logger.info(f"Calling policy re-ranking LLM ({rerank_client.model_name}) for {len(items_to_rank)} policies...")

        ranked_items_data = await rerank_client.rerank_items(
            items=items_to_rank,
            prompt_template=prompt_template,
            prompt_context=prompt_context
        )
        logger.info(f"Policy re-ranking LLM returned {len(ranked_items_data)} potentially relevant policies.")

        # --- Map re-ranked data back ---
        ranked_policies = []
        original_items_map = {item.id: item for item in initial_policies_list}
        processed_ids = set()
        for item_data in ranked_items_data:
             item_id = item_data.get("id")
             if item_id in original_items_map and item_id not in processed_ids:
                 ranked_policies.append(original_items_map[item_id])
                 processed_ids.add(item_id)
             else:
                 logger.warning(f"Policy re-ranking mapping encountered unknown/duplicate ID: {item_id}")

        logger.info(f"Final re-ranked policy count: {len(ranked_policies)}.")
        return ranked_policies

    except (ValueError, NotImplementedError) as config_err:
         logger.error(f"LLM client configuration error for policy re-ranking: {config_err}", exc_info=False)
         logger.warning("Falling back to original policy order due to configuration error.")
         return initial_policies_list
    except Exception as e:
         logger.exception("Unexpected error during policy re-ranking.")
         logger.warning("Falling back to original policy order due to unexpected error.")
         return initial_policies_list