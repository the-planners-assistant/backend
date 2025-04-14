# app/services/policies_service.py
import random
import asyncio
from typing import List
import logging # Import logging

from app.models.schemas import LocationInput, PolicyInfo
from app.data.mock_data import MOCK_POLICIES # Import mock data
from app.llm_clients import get_llm_client # Import the factory

logger = logging.getLogger(__name__) # Get logger instance

async def get_policies_for_location(location: LocationInput) -> List[PolicyInfo]:
    """
    Service function to retrieve relevant policies for a location.
    Placeholder: Returns a random subset of mock policies, then re-ranks using JSON mode.
    Replace mock fetching with actual DB lookup or AI policy analysis logic.
    """
    logger.info(f"Fetching policies for Lat: {location.lat}, Lon: {location.lon}")
    # Simulate delay
    fetch_delay = random.uniform(0.1, 0.3)
    logger.debug(f"Simulating initial policy fetch delay: {fetch_delay:.2f}s")
    await asyncio.sleep(fetch_delay)

    # --- Start: Replace with actual logic ---
    # Mock logic: Use all mock policies for demonstration
    initial_policies_data = MOCK_POLICIES
    logger.debug("Using mock data for initial policies.")
    # --- End: Replace with actual logic ---

    # Map initial results to Pydantic model
    initial_policies_list = [
        PolicyInfo(id=p["id"], description=p["description"]) for p in initial_policies_data
    ]
    logger.info(f"Found {len(initial_policies_list)} initial policies.")

    # --- Re-ranking Step ---
    if not initial_policies_list:
         logger.info("No initial policies found to re-rank.")
         return []

    try:
        logger.debug("Attempting to get re-ranking LLM client.")
        rerank_client = get_llm_client(client_type="reranking")
        items_to_rank = [p.model_dump() for p in initial_policies_list]
        context = f"Relevance context: Planning policies for location lat={location.lat}, lon={location.lon}."
        logger.debug(f"Context for re-ranking (truncated): {context[:150]}...")

        logger.info(f"Calling re-ranking LLM ({rerank_client.model_name}) requesting JSON...")
        # Call the abstract method - client handles JSON request & parsing
        ranked_items_data = await rerank_client.rerank_items(
            items=items_to_rank,
            context=context
            # Example: pass temperature if needed kwargs={'temperature': 0.1}
        )
        logger.info(f"Re-ranking LLM returned {len(ranked_items_data)} potentially relevant items.")

        # Map re-ranked data back to PolicyInfo list
        ranked_policies = []
        original_items_map = {item.id: item for item in initial_policies_list}
        processed_ids = set()

        # ranked_items_data should be the list of dicts corresponding to the ranked IDs
        for item_data in ranked_items_data:
             item_id = item_data.get("id")
             if item_id in original_items_map and item_id not in processed_ids:
                 logger.debug(f"Adding ranked item ID: {item_id}")
                 ranked_policies.append(original_items_map[item_id])
                 processed_ids.add(item_id)
             else:
                 # This might happen if the LLM hallucinates an ID or repeats one
                 logger.warning(f"Re-ranking post-processing encountered unknown/duplicate ID in LLM output: {item_id}")

        logger.info(f"Final re-ranked policy count: {len(ranked_policies)}.")
        return ranked_policies

    except (ValueError, NotImplementedError) as config_err:
         # Handle client configuration errors specifically
         logger.error(f"LLM client configuration error for re-ranking: {config_err}", exc_info=False)
         logger.warning("Falling back to original policy order due to configuration error.")
         return initial_policies_list
    except Exception as e:
         # Catch other unexpected errors during re-ranking call
         logger.exception("Unexpected error during policy re-ranking.")
         logger.warning("Falling back to original policy order due to unexpected error.")
         return initial_policies_list # Fallback to unranked list