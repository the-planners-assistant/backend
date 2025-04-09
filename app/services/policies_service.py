# app/services/policies_service.py
import random
import asyncio
from typing import List
from app.models.schemas import LocationInput, PolicyInfo
from app.data.mock_data import MOCK_POLICIES # Import mock data

async def get_policies_for_location(location: LocationInput) -> List[PolicyInfo]:
    """
    Service function to retrieve relevant policies for a location.
    Placeholder: Returns a random subset of mock policies.
    Replace with actual DB lookup or AI policy analysis logic.
    """
    print(f"SERVICE: Fetching policies for Lat: {location.lat}, Lon: {location.lon}")
    # Simulate delay (DB query / initial AI filter)
    await asyncio.sleep(random.uniform(0.3, 0.8))

    # --- Start: Replace with actual logic ---
    # Example: Fetch policies based on area type or run initial AI check
    # results = await db.query(...) or await ai_policy_client.get_relevant_policies(...)

    # Mock logic:
    num_policies = random.randint(1, len(MOCK_POLICIES))
    relevant_policies_data = random.sample(MOCK_POLICIES, num_policies)
    # --- End: Replace with actual logic ---

    # Map results to Pydantic model
    policies_list = [
        PolicyInfo(id=p["id"], description=p["description"]) for p in relevant_policies_data
    ]

    print(f"SERVICE: Found {len(policies_list)} policies.")
    return policies_list