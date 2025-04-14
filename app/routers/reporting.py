# app/routers/reporting.py
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Depends
from typing import Optional # Added Optional
import logging # Import logging
import io # For BytesIO

from app.models import schemas
from app.services import reporting_service
from app.core.config import settings

logger = logging.getLogger(__name__) # Get logger instance

router = APIRouter(
    tags=["Reporting"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/generate_report", # Endpoint path
    response_model=schemas.AsyncTaskResponse, # Respond with task info
    status_code=status.HTTP_202_ACCEPTED, # Use 202 Accepted status code
    summary="Trigger AI Planning Report Generation (No Photo)",
    description="Triggers asynchronous generation of an AI-assisted planning report based on location and proposal details (text only). Returns a task ID for status polling."
)
async def trigger_ai_report(report_input: schemas.ReportInput):
    """
    API endpoint to trigger asynchronous report generation.
    Returns a task ID for polling status/results.
    - **report_input**: Includes location and optional proposal text.
    """
    logger.info(f"Received trigger report request (text only) for lat={report_input.lat}, lon={report_input.lon}")
    logger.debug(f"Proposal text: {report_input.proposal_text[:100] if report_input.proposal_text else 'N/A'}...")
    try:
        # Call service to enqueue the task
        # Pass report_input directly, service should handle serialization if needed
        task_id = await reporting_service.trigger_report_generation(report_input)

        logger.info(f"Triggered report generation task with ID: {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")
    except Exception as e:
        logger.exception("Error triggering report generation (text only).")
        raise HTTPException(status_code=500, detail="Internal server error while triggering report.")


# --- Example endpoint for handling file uploads ---
# Note: Requires corresponding service function modifications
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
    aerial_photo: UploadFile = File(...) # Accept the uploaded file
):
    """
    Triggers report generation including analysis of an aerial photo.
    """
    logger.info(f"Received report request with photo upload for lat={lat}, lon={lon}")
    logger.debug(f"Uploaded filename: {aerial_photo.filename}, content type: {aerial_photo.content_type}")
    logger.debug(f"Proposal text: {proposal_text[:100] if proposal_text else 'N/A'}...")

    # --- Basic File Validation ---
    if not aerial_photo.content_type or not aerial_photo.content_type.startswith("image/"):
         logger.warning(f"Invalid file type uploaded: {aerial_photo.content_type}")
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    # --- Prepare Input for Service ---
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
         # Ensure file handle is closed (FastAPI might do this, but good practice)
         await aerial_photo.close()

    # Create the input structure for the service/task
    report_input = schemas.ReportInput(lat=lat, lon=lon, proposal_text=proposal_text)

    # --- Call Service to Trigger Task ---
    try:
        # Ensure reporting_service has a function that accepts the file bytes/IO
        # This is a conceptual call - implementation needed in service
        logger.debug("Calling service to trigger report generation with photo...")
        task_id = await reporting_service.trigger_report_generation_with_photo(
             report_input=report_input,
             photo_data=photo_bytes_io,
             photo_mime_type=aerial_photo.content_type
         )
        # NOTE: trigger_report_generation_with_photo needs to be implemented
        # in reporting_service.py. It should handle uploading the file via
        # the LLM client and passing necessary info (like file URI) to the Celery task.

        logger.info(f"Triggered report generation task with photo, Task ID: {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")

    except NotImplementedError:
         logger.error("Service function 'trigger_report_generation_with_photo' not implemented.")
         raise HTTPException(status_code=501, detail="Report generation with photo is not yet implemented.")
    except Exception as e:
        logger.exception("Error triggering report generation with photo.")
        raise HTTPException(status_code=500, detail="Internal server error triggering report.")


# Add other reporting endpoints if needed