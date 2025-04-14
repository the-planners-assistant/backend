# app/services/reporting_service.py
from app.models import schemas
from app.tasks import generate_report_task
from celery.result import AsyncResult
import logging
from typing import Optional
from io import BytesIO
import asyncpg
from fastapi import Depends

from app.services import constraints_service, policies_service
from app.db import get_db_connection
from app.llm_clients import get_llm_client
from app.utils.geo_utils import reverse_geocode, get_static_map_image, get_street_view_image
import asyncio # Import asyncio

logger = logging.getLogger(__name__)

async def _upload_image_to_gemini(image_bytes: bytes, mime_type: str, display_name: str) -> Optional[str]:
    # (Helper function remains the same)
    if not image_bytes: return None
    try:
        upload_client = get_llm_client(client_type="reporting")
        image_data = BytesIO(image_bytes)
        uploaded_file_obj = await upload_client.upload_file(file_data=image_data, mime_type=mime_type, display_name=display_name)
        return uploaded_file_obj.uri
    except Exception as e: logger.error(f"Failed upload {display_name}: {e}", exc_info=True); return None


async def trigger_report_generation(
    report_input: schemas.ReportInput,
    conn: asyncpg.Connection # Accept connection as argument
    ) -> str:
    """
    Gets address, fetches images, uploads images, fetches/ranks constraints & policies,
    then triggers the async report task with image URIs.
    """
    task_id = "error_task_id"
    logger.info(f"Service: Starting report generation process for lat={report_input.lat}, lon={report_input.lon}")
    aerial_uri: Optional[str] = None
    street_uri: Optional[str] = None

    try:
        # --- Parallel Fetching (Address & Images) ---
        logger.debug("Fetching address and images concurrently...")
        address_task = asyncio.create_task(reverse_geocode(report_input.lat, report_input.lon))
        aerial_task = asyncio.create_task(get_static_map_image(report_input.lat, report_input.lon))
        street_task = asyncio.create_task(get_street_view_image(report_input.lat, report_input.lon))

        formatted_address, aerial_bytes, street_bytes = await asyncio.gather(
            address_task, aerial_task, street_task
        )
        logger.info(f"Formatted address: {formatted_address}")
        logger.info(f"Fetched aerial image: {len(aerial_bytes) if aerial_bytes else 'No'} bytes.")
        logger.info(f"Fetched street view image: {len(street_bytes) if street_bytes else 'No'} bytes.")

        # --- Parallel Uploading ---
        logger.debug("Uploading images to Gemini File API concurrently...")
        aerial_upload_task = asyncio.create_task(
            _upload_image_to_gemini(aerial_bytes, "image/jpeg", f"aerial_{report_input.lat}_{report_input.lon}.jpg")
        ) if aerial_bytes else asyncio.create_task(asyncio.sleep(0, result=None))
        street_upload_task = asyncio.create_task(
             _upload_image_to_gemini(street_bytes, "image/jpeg", f"street_{report_input.lat}_{report_input.lon}.jpg")
        ) if street_bytes else asyncio.create_task(asyncio.sleep(0, result=None))

        # --- Parallel Dependency Fetching ---
        logger.debug("Fetching and ranking constraints & policies concurrently...")
        constraints_task = asyncio.create_task( constraints_service.get_constraints_for_location( location=schemas.LocationInput(lat=report_input.lat, lon=report_input.lon), conn=conn ))
        policies_task = asyncio.create_task( policies_service.get_policies_for_location( location=schemas.LocationInput(lat=report_input.lat, lon=report_input.lon) ))

        # --- Gather all results ---
        aerial_uri, street_uri, ranked_constraints, ranked_policies = await asyncio.gather(
             aerial_upload_task, street_upload_task, constraints_task, policies_task
        )
        logger.info(f"Fetched/Ranked {len(ranked_constraints)} constraints and {len(ranked_policies)} policies.")
        logger.info(f"Aerial URI: {aerial_uri}, Street View URI: {street_uri}")

        # --- Prepare Input for Celery Task ---
        # Remove mime types as they are not used in the task anymore
        task_input_data = schemas.ReportTaskInput(
            request=report_input,
            formatted_address=formatted_address,
            ranked_constraints=ranked_constraints,
            ranked_policies=ranked_policies,
            aerial_photo_uri=aerial_uri,
            street_view_photo_uri=street_uri
        )

        # --- Enqueue Task ---
        logger.debug("Enqueueing generate_report_task...")
        task = generate_report_task.delay(task_input_data.model_dump())
        task_id = task.id
        logger.info(f"Task {task_id} enqueued successfully.")
        return task_id

    except Exception as e:
        logger.exception(f"Failed during report generation service execution for {report_input.lat},{report_input.lon}")
        raise

# (trigger_report_generation_with_photo removed as this function now handles optional images)