# app/services/constraints_service.py
import random
import time
import asyncio # Import asyncio for potential async sleep
from typing import List
from app.models.schemas import LocationInput, ConstraintInfo
from app.data.mock_data import MOCK_CONSTRAINTS # Import mock data

async def get_constraints_for_location(location: LocationInput) -> List[ConstraintInfo]:
    """
    Service function to retrieve constraints for a given location.
    Placeholder: Returns a random subset of mock constraints.
    Replace with actual DB/GIS lookup logic.
    """
    print(f"SERVICE: Fetching constraints for Lat: {location.lat}, Lon: {location.lon}")
    # Use asyncio.sleep for non-blocking delay in async function
    await asyncio.sleep(random.uniform(0.2, 0.6))

    # --- Start: Replace with actual logic ---
    # Example: Query PostGIS database based on location geometry using an async DB driver
    # results = await db_session.execute(
    #     select(ConstraintTable).where(ST_Intersects(ConstraintTable.geom, ...))
    # )
    # found_constraints_data = [parse_db_result(r) for r in results.scalars().all()]

    # Mock logic:
    num_constraints = random.randint(0, len(MOCK_CONSTRAINTS))
    found_constraints_data = random.sample(MOCK_CONSTRAINTS, num_constraints)
    # --- End: Replace with actual logic ---

    # Map results to Pydantic model
    constraints_list = [
        ConstraintInfo(
            id=c["id"],
            name=c["name"],
            type=c["type"],
            explanation_available=c.get("explanation", False)
        ) for c in found_constraints_data
    ]

    print(f"SERVICE: Found {len(constraints_list)} constraints.")
    return constraints_list