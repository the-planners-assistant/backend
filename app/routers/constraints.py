# app/routers/constraints.py
from fastapi import APIRouter, HTTPException, Depends # Import Depends
from typing import List
import asyncpg # Import asyncpg for type hinting

from app.models import schemas
from app.services import constraints_service
# Import the dependency function (adjust path if necessary)
from app.db import get_db_connection

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
    # *** Declare the database connection dependency here ***
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    API endpoint to fetch constraints.
    - **location**: Input latitude and longitude.
    - **conn**: Database connection injected by FastAPI.
    """
    try:
        print(f"ROUTER: Received constraints request for {location.model_dump_json()}")
        print(f"ROUTER DEBUG: Type of 'conn' received from DI: {type(conn)}") # Debug point

        # *** Pass the resolved connection 'conn' to the service function ***
        constraints_list = await constraints_service.get_constraints_for_location(location=location, conn=conn)

        response_data = schemas.ConstraintsResponse(
            location=location,
            constraints=constraints_list
        )
        print(f"ROUTER: Sending {len(constraints_list)} constraints.")
        return response_data
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions raised by the service layer or dependency
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        print(f"ROUTER: Unhandled error processing constraints request: {type(e).__name__} - {e}")
        # Consider logging traceback
        raise HTTPException(status_code=500, detail="Internal server error processing constraints request.")