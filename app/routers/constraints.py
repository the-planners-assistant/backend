# app/routers/constraints.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
import asyncpg
import logging # Import logging

from app.models import schemas
from app.services import constraints_service
from app.db import get_db_connection

logger = logging.getLogger(__name__) # Get logger instance

# Define the router
router = APIRouter(
    tags=["Constraints"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/constraints",
    response_model=schemas.ConstraintsResponse,
    summary="Get Planning Constraints",
    description="Retrieves relevant planning constraints based on geographic location."
)
async def get_constraints(
    location: schemas.LocationInput,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    API endpoint to fetch constraints.
    - **location**: Input latitude and longitude.
    - **conn**: Database connection injected by FastAPI.
    """
    logger.info(f"Received constraints request for lat={location.lat}, lon={location.lon}")
    logger.debug(f"Using database connection: {type(conn)}") # Log type, not connection object itself

    try:
        constraints_list = await constraints_service.get_constraints_for_location(location=location, conn=conn)

        response_data = schemas.ConstraintsResponse(
            location=location,
            constraints=constraints_list
        )
        logger.info(f"Returning {len(constraints_list)} constraints.")
        logger.debug(f"Response data sample (first constraint): {constraints_list[0] if constraints_list else 'None'}")
        return response_data
    except HTTPException as http_exc:
        # Log and re-raise HTTPExceptions raised by the service layer or dependency
        logger.error(f"HTTPException in constraints endpoint: {http_exc.status_code} - {http_exc.detail}", exc_info=False) # No need for traceback here
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception("Unhandled error processing constraints request.") # Logs exception info automatically
        raise HTTPException(status_code=500, detail="Internal server error processing constraints request.")