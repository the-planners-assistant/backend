# app/services/reporting_service.py
from app.models import schemas
from app.tasks import generate_report_task
from celery.result import AsyncResult
import logging # Import logging
from typing import Optional # For optional types
from io import BytesIO # For file data

logger = logging.getLogger(__name__) # Get logger instance

# --- Function for text-only report ---
async def trigger_report_generation(report_input: schemas.ReportInput) -> str:
    """
    Service function to trigger the asynchronous report generation task (text only).
    Returns the task ID.
    """
    logger.info(f"Triggering text-only report generation task for lat={report_input.lat}, lon={report_input.lon}")
    # Log truncated proposal text
    proposal_preview = report_input.proposal_text[:100] + "..." if report_input.proposal_text and len(report_input.proposal_text) > 100 else report_input.proposal_text or "N/A"
    logger.debug(f"Proposal preview: {proposal_preview}")

    try:
        # Send task to the queue. Pass data as a serializable dict using .model_dump()
        # Ensure all data within report_input is JSON-serializable
        task = generate_report_task.delay(report_input.model_dump())
        logger.info(f"Task {task.id} enqueued successfully.")
        return task.id
    except Exception as e:
        logger.exception(f"Failed to enqueue report generation task for {report_input.lat},{report_input.lon}")
        # Re-raise or handle appropriately depending on desired API behavior
        raise


# --- Conceptual function for report with photo ---
# NOTE: This function needs implementation details for file handling & task modification
async def trigger_report_generation_with_photo(
    report_input: schemas.ReportInput,
    photo_data: BytesIO,
    photo_mime_type: str
) -> str:
    """
    Service function to trigger asynchronous report generation including a photo.
    (Needs implementation: Upload photo, pass file info to task)
    Returns the task ID.
    """
    logger.info(f"Triggering report generation task with photo for lat={report_input.lat}, lon={report_input.lon}")
    logger.debug(f"Received photo data, mime_type: {photo_mime_type}")

    uploaded_file_uri = None
    uploaded_file_name = None
    try:
        # --- Upload Photo using LLM Client ---
        # Needs the LLM client factory here too
        from app.llm_clients import get_llm_client
        # Decide which client handles uploads (reporting or a general one?)
        # Let's assume the reporting client can upload
        upload_client = get_llm_client(client_type="reporting") # Or a dedicated upload client/service
        logger.debug("Uploading photo using LLM client...")

        # Use a meaningful display name if possible
        display_name = f"aerial_photo_{report_input.lat}_{report_input.lon}.png" # Example name

        uploaded_file_obj = await upload_client.upload_file(
            file_data=photo_data,
            mime_type=photo_mime_type,
            display_name=display_name
        )
        uploaded_file_uri = uploaded_file_obj.uri
        uploaded_file_name = uploaded_file_obj.name
        logger.info(f"Photo uploaded successfully via File API: URI={uploaded_file_uri}, Name={uploaded_file_name}")

        # --- Prepare Task Input ---
        # Add file information to the data sent to the Celery task
        report_input_dict = report_input.model_dump()
        report_input_dict["aerial_photo_uri"] = uploaded_file_uri
        report_input_dict["aerial_photo_mime_type"] = photo_mime_type
        report_input_dict["aerial_photo_name"] = uploaded_file_name # Pass name for potential deletion later?

        # --- Enqueue Task ---
        logger.debug(f"Enqueuing task with photo URI: {uploaded_file_uri}")
        # *** IMPORTANT: Ensure generate_report_task in tasks.py can handle these new keys ***
        task = generate_report_task.delay(report_input_dict)
        logger.info(f"Task {task.id} with photo enqueued successfully.")
        return task.id

    except Exception as e:
        # Log exception during upload or enqueueing
        logger.exception(f"Failed during report generation triggering with photo for {report_input.lat},{report_input.lon}")
        # Optional: Attempt to delete the uploaded file if enqueueing failed? Requires file name.
        # if uploaded_file_name:
        #     logger.warning(f"Attempting to clean up uploaded file {uploaded_file_name} due to error.")
        #     # Add cleanup logic if needed...
        raise # Re-raise the error to be caught by the router


# The actual long-running logic (_run_actual_complex_generation) resides
# conceptually within or is called by the Celery task defined in app/tasks.py