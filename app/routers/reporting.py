# app/routers/reporting.py
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Depends
from typing import Optional
import logging
import io
import asyncpg # Import asyncpg

from app.models import schemas
from app.services import reporting_service
from app.core.config import settings
from app.db import get_db_connection # Import DB dependency function

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Reporting"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/generate_report",
    response_model=schemas.AsyncTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI Planning Report Generation (No Photo)",
    description="Triggers asynchronous generation of an AI-assisted planning report based on location and proposal details (text only). Returns a task ID for status polling."
)
async def trigger_ai_report(
    report_input: schemas.ReportInput,
    conn: asyncpg.Connection = Depends(get_db_connection) # <-- Inject DB connection HERE
    ):
    """
    API endpoint to trigger asynchronous report generation.
    Injects DB connection and passes it to the service.
    """
    logger.info(f"Received trigger report request (text only) for lat={report_input.lat}, lon={report_input.lon}")
    logger.debug(f"Proposal text: {report_input.proposal_text[:100] if report_input.proposal_text else 'N/A'}...")
    try:
        # --- Pass the resolved connection object to the service ---
        task_id = await reporting_service.trigger_report_generation(
            report_input=report_input,
            conn=conn # <-- Pass resolved connection
        )

        logger.info(f"Triggered report generation task with ID: {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")
    except Exception as e:
        logger.exception("Error triggering report generation (text only).")
        # Check if it's an HTTPException from the service and re-raise, otherwise wrap
        if isinstance(e, HTTPException):
             raise e
        raise HTTPException(status_code=500, detail=f"Internal server error triggering report: {type(e).__name__}")


# --- Endpoint for handling file uploads ---
@router.post(
    "/generate_report_with_photo",
    response_model=schemas.AsyncTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Report Generation with Aerial Photo",
    description="Triggers asynchronous report generation including analysis of an aerial photo. Returns a task ID for status polling."
)
async def trigger_report_with_photo(
    # Use Form for text fields when mixing with File uploads
    lat: float = Form(...),
    lon: float = Form(...),
    proposal_text: Optional[str] = Form(None),
    aerial_photo: UploadFile = File(...),
    conn: asyncpg.Connection = Depends(get_db_connection) # <-- Inject DB connection HERE
):
    """
    Triggers report generation including analysis of an aerial photo.
    Injects DB connection and passes it to the service.
    """
    logger.info(f"Received report request with photo upload for lat={lat}, lon={lon}")
    logger.debug(f"Uploaded filename: {aerial_photo.filename}, content type: {aerial_photo.content_type}")
    logger.debug(f"Proposal text: {proposal_text[:100] if proposal_text else 'N/A'}...")

    if not aerial_photo.content_type or not aerial_photo.content_type.startswith("image/"):
         logger.warning(f"Invalid file type uploaded: {aerial_photo.content_type}")
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    photo_bytes_io: Optional[io.BytesIO] = None
    try:
         logger.debug("Reading uploaded file into memory...")
         file_content = await aerial_photo.read()
         photo_bytes_io = io.BytesIO(file_content)
         logger.debug(f"Read {len(file_content)} bytes from uploaded file.")
    except Exception as e:
         logger.exception("Failed to read uploaded file.")
         raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")
    finally:
         await aerial_photo.close()

    report_input = schemas.ReportInput(lat=lat, lon=lon, proposal_text=proposal_text)

    try:
        logger.debug("Calling service to trigger report generation with photo...")
        # --- Pass the resolved connection object to the service ---
        task_id = await reporting_service.trigger_report_generation_with_photo(
             report_input=report_input,
             photo_data=photo_bytes_io,
             photo_mime_type=aerial_photo.content_type,
             conn=conn # <-- Pass resolved connection
         )

        logger.info(f"Triggered report generation task with photo, Task ID: {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")

    except NotImplementedError:
         logger.error("Service function 'trigger_report_generation_with_photo' not implemented.")
         raise HTTPException(status_code=501, detail="Report generation with photo is not yet implemented.")
    except Exception as e:
        logger.exception("Error triggering report generation with photo.")
        if isinstance(e, HTTPException):
             raise e
        raise HTTPException(status_code=500, detail=f"Internal server error triggering report: {type(e).__name__}")