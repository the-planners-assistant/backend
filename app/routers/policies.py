# app/routers/policies.py
from fastapi import APIRouter, HTTPException

from app.models import schemas
from app.services import policies_service
from app.core.config import settings

router = APIRouter(
    tags=["Policies"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/policies",
    response_model=schemas.PoliciesResponse,
    summary="Get Relevant Planning Policies",
    description="Retrieves relevant planning policies based on geographic location."
)
async def get_policies(location: schemas.LocationInput):
    """
    API endpoint to fetch relevant policies.
    - **location**: Input latitude and longitude.
    """
    try:
        print(f"ROUTER: Received policies request for {location.model_dump_json()}")
        policies_list = await policies_service.get_policies_for_location(location)

        response_data = schemas.PoliciesResponse(
            location=location,
            policies=policies_list
        )
        print(f"ROUTER: Sending {len(policies_list)} policies.")
        return response_data
    except Exception as e:
        print(f"ROUTER: Error fetching policies: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching policies.")

# Add other policy-related endpoints here