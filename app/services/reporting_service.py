# app/services/reporting_service.py
from app.models import schemas
from app.tasks import generate_report_task
from celery.result import AsyncResult
import logging
from typing import Optional, List # Added List
from io import BytesIO
import asyncpg
from fastapi import Depends # Keep Depends if service *could* be injected elsewhere needing DB
import asyncio

from app.services import constraints_service, policies_service
from app.db import get_db_connection # Keep if Depends is used
from app.llm_clients import get_llm_client
from app.utils.geo_utils import reverse_geocode, get_static_map_image, get_street_view_image

logger = logging.getLogger(__name__)

# Helper to upload image bytes and return URI
async def _upload_media_to_gemini(
    media_bytes: bytes,
    mime_type: str,
    display_name: str
) -> Optional[str]:
    """Uploads media bytes using Gemini File API and returns the URI."""
    if not media_bytes:
        return None
    try:
        upload_client = get_llm_client(client_type="reporting") # Or dedicated upload client
        media_data = BytesIO(media_bytes)
        # Using asyncio.to_thread for the synchronous SDK upload call
        uploaded_file_obj = await asyncio.to_thread(
            upload_client.client.files.upload, # Access sync client.files directly
            file=media_data,
            config={"mime_type": mime_type, "display_name": display_name}
        )
        logger.info(f"Media uploaded: Name={uploaded_file_obj.name}, URI={uploaded_file_obj.uri}")
        return uploaded_file_obj.uri
    except Exception as e:
        logger.error(f"Failed to upload {display_name} to Gemini File API: {e}", exc_info=True)
        return None


# --- Main function to trigger report generation ---
async def trigger_report_generation(
    report_input: schemas.ReportInput,
    conn: asyncpg.Connection, # Accept connection as argument
    # Add arguments for future document uploads
    # document_files: Optional[List[BytesIO]] = None,
    # document_mime_types: Optional[List[str]] = None
    ) -> str:
    """
    Gets address, fetches/uploads images & documents, fetches/ranks constraints & policies,
    then triggers the async report task with all context URIs.
    """
    task_id = "error_task_id"
    logger.info(f"Service: Starting report generation process for lat={report_input.lat}, lon={report_input.lon}")
    aerial_uri: Optional[str] = None
    street_uri: Optional[str] = None
    document_uris: List[str] = [] # For future use

    try:
        # --- Parallel Fetching (Address, Images) ---
        logger.debug("Fetching address and images concurrently...")
        address_task = asyncio.create_task(reverse_geocode(report_input.lat, report_input.lon))
        aerial_task = asyncio.create_task(get_static_map_image(report_input.lat, report_input.lon))
        street_task = asyncio.create_task(get_street_view_image(report_input.lat, report_input.lon))

        # Gather initial fetches
        formatted_address, aerial_bytes, street_bytes = await asyncio.gather(
            address_task, aerial_task, street_task
        )
        logger.info(f"Formatted address: {formatted_address}")
        logger.info(f"Fetched aerial image: {len(aerial_bytes) if aerial_bytes else 'No'} bytes.")
        logger.info(f"Fetched street view image: {len(street_bytes) if street_bytes else 'No'} bytes.")

        # --- Prepare Upload Tasks ---
        upload_tasks = []
        if aerial_bytes:
            upload_tasks.append(asyncio.create_task(
                _upload_media_to_gemini(aerial_bytes, "image/jpeg", f"aerial_{report_input.lat}_{report_input.lon}.jpg")
            ))
        if street_bytes:
             upload_tasks.append(asyncio.create_task(
                 _upload_media_to_gemini(street_bytes, "image/jpeg", f"street_{report_input.lat}_{report_input.lon}.jpg")
             ))
        # Add document upload tasks here when implemented
        # if document_files and document_mime_types:
        #     for i, doc_file in enumerate(document_files):
        #         mime = document_mime_types[i]
        #         # Use original filename if available, otherwise generate one
        #         doc_display_name = f"doc_{i+1}_{report_input.lat}_{report_input.lon}"
        #         upload_tasks.append(asyncio.create_task(
        #             _upload_media_to_gemini(doc_file.getvalue(), mime, doc_display_name)
        #         ))

        # --- Parallel Dependency Fetching ---
        logger.debug("Fetching and ranking constraints & policies concurrently...")
        constraints_task = asyncio.create_task( constraints_service.get_constraints_for_location( location=schemas.LocationInput(lat=report_input.lat, lon=report_input.lon), conn=conn ))
        policies_task = asyncio.create_task( policies_service.get_policies_for_location( location=schemas.LocationInput(lat=report_input.lat, lon=report_input.lon) ))

        # --- Gather all results (Uploads + Fetches) ---
        # Group upload results separately first if needed for clarity
        logger.debug(f"Waiting for {len(upload_tasks)} uploads and 2 dependency fetches...")
        all_tasks = upload_tasks + [constraints_task, policies_task]
        results = await asyncio.gather(*all_tasks)

        # Extract results
        upload_uris = results[:len(upload_tasks)]
        ranked_constraints = results[len(upload_tasks)]
        ranked_policies = results[len(upload_tasks)+1]

        # Assign URIs based on original order (could be more robust)
        uri_idx = 0
        if aerial_bytes: aerial_uri = upload_uris[uri_idx]; uri_idx += 1
        if street_bytes: street_uri = upload_uris[uri_idx]; uri_idx += 1
        # Extract document URIs similarly when implemented

        logger.info(f"Fetched/Ranked {len(ranked_constraints)} constraints and {len(ranked_policies)} policies.")
        logger.info(f"Aerial URI: {aerial_uri}, Street View URI: {street_uri}")
        # logger.info(f"Document URIs: {document_uris}") # Add when implemented

        # --- Prepare Input for Celery Task ---
        task_input_data = schemas.ReportTaskInput(
            request=report_input,
            formatted_address=formatted_address,
            ranked_constraints=ranked_constraints,
            ranked_policies=ranked_policies,
            aerial_photo_uri=aerial_uri,
            street_view_photo_uri=street_uri,
            # document_uris=document_uris, # Add when implemented
        )

        # --- Enqueue Task ---
        logger.debug("Enqueueing generate_report_task...")
        task = generate_report_task.delay(task_input_data.model_dump())
        task_id = task.id
        logger.info(f"Task {task_id} enqueued successfully.")
        return task_id

    except Exception as e:
        logger.exception(f"Failed during report generation service execution for {report_input.lat},{report_input.lon}")
        # Consider cleanup of uploaded files here if needed
        raise