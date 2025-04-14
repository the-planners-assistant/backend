# app/routers/policies.py
from fastapi import APIRouter, HTTPException
import logging # Import logging

from app.models import schemas
from app.services import policies_service
from app.core.config import settings

logger = logging.getLogger(__name__) # Get logger instance

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
    logger.info(f"Received policies request for lat={location.lat}, lon={location.lon}")
    try:
        policies_list = await policies_service.get_policies_for_location(location)

        response_data = schemas.PoliciesResponse(
            location=location,
            policies=policies_list
        )
        logger.info(f"Returning {len(policies_list)} policies after potential re-ranking.")
        logger.debug(f"Policies response sample (first policy ID): {policies_list[0].id if policies_list else 'None'}")
        return response_data
    except Exception as e:
        logger.exception("Unhandled error fetching policies.") # Logs exception info
        raise HTTPException(status_code=500, detail="Internal server error while fetching policies.")

# Add other policy-related endpoints here