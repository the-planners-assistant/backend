# app/routers/reporting.py
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Depends
from typing import Optional
import logging
import io
import asyncpg

from app.models import schemas
from app.services import reporting_service
from app.core.config import settings
from app.db import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Reporting"],
    responses={404: {"description": "Not found"}},
)

# --- Endpoint for Report Generation (Always fetches images) ---
# Renamed from /generate_report_with_photo
@router.post(
    "/generate_report", # Renamed endpoint path
    response_model=schemas.AsyncTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI Planning Report Generation",
    description=(
        "Triggers asynchronous generation of an AI-assisted planning report. "
        "Requires location (lat/lon) and optional proposal text. "
        "Automatically fetches relevant aerial and street view images as context. "
        "Returns a task ID for status polling."
    )
)
async def trigger_report( # Renamed function
    # Use Form for parameters as file uploads might be added later
    lat: float = Form(...),
    lon: float = Form(...),
    proposal_text: Optional[str] = Form(None),
    # Add document uploads later:
    # documents: Optional[List[UploadFile]] = File(None),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Triggers report generation. Fetches images, constraints, policies,
    and queues the background task.
    """
    logger.info(f"Received trigger report request for lat={lat}, lon={lon}")
    logger.debug(f"Proposal text: {proposal_text[:100] if proposal_text else 'N/A'}...")
    # Add logging for document uploads when implemented

    report_input = schemas.ReportInput(lat=lat, lon=lon, proposal_text=proposal_text)

    # --- Handle potential future document uploads ---
    # When documents parameter is added:
    # 1. Check content types (e.g., application/pdf, application/msword, etc.)
    # 2. Read document bytes: doc_bytes_io_list = [io.BytesIO(await doc.read()) for doc in documents]
    # 3. Pass doc_bytes_io_list and mime types to the service function.
    # For now, we pass None for document-related arguments to the service.

    try:
        logger.debug("Calling service to trigger report generation...")
        # Use the service function that handles image fetching/uploading
        # Assuming trigger_report_generation now incorporates image logic
        task_id = await reporting_service.trigger_report_generation(
             report_input=report_input,
             conn=conn
             # Add document arguments here when implemented:
             # document_files=doc_bytes_io_list,
             # document_mime_types=[doc.content_type for doc in documents]
         )

        logger.info(f"Triggered report generation task, Task ID: {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")

    # (Error handling remains similar)
    except NotImplementedError:
         logger.error("Required service function not implemented or misconfigured.")
         raise HTTPException(status_code=501, detail="Report generation service is not correctly configured.")
    except Exception as e:
        logger.exception("Error triggering report generation.")
        if isinstance(e, HTTPException):
             raise e
        raise HTTPException(status_code=500, detail=f"Internal server error triggering report: {type(e).__name__}")