# app/routers/constraints.py
from fastapi import APIRouter, HTTPException
from typing import List

from app.models import schemas # Import schemas
from app.services import constraints_service # Import the specific service
from app.core.config import settings # Import settings for API prefix

# Define the router
router = APIRouter(
    # prefix is now handled globally in main.py
    tags=["Constraints"], # Tag for API documentation
    responses={404: {"description": "Not found"}}, # Example default response
)

@router.post(
    "/constraints", # Endpoint path relative to global prefix
    response_model=schemas.ConstraintsResponse, # Use schema for response validation
    summary="Get Planning Constraints",
    description="Retrieves relevant planning constraints based on geographic location."
)
async def get_constraints(location: schemas.LocationInput):
    """
    API endpoint to fetch constraints.
    - **location**: Input latitude and longitude.
    """
    try:
        print(f"ROUTER: Received constraints request for {location.model_dump_json()}")
        # Call the service layer function
        constraints_list = await constraints_service.get_constraints_for_location(location)

        # Structure the response using the Pydantic model
        response_data = schemas.ConstraintsResponse(
            location=location,
            constraints=constraints_list
        )
        print(f"ROUTER: Sending {len(constraints_list)} constraints.")
        return response_data
    except Exception as e:
        # Basic error handling - add more specific exceptions later
        print(f"ROUTER: Error fetching constraints: {type(e).__name__} - {e}")
        # Consider logging the full traceback here in real application
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching constraints.")

# Add other constraint-related endpoints here