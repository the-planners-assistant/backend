# app/routers/tasks_router.py
from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult
from app.celery_app import celery_app
from app.models import schemas
from app.core.config import settings
from typing import Any
import logging # Import logging

logger = logging.getLogger(__name__) # Get logger instance

router = APIRouter(
    tags=["Task Status"],
    responses={404: {"description": "Task not found"}},
)

@router.get(
    "/tasks/{task_id}/status",
    response_model=schemas.TaskStatusResponse,
    summary="Get Background Task Status and Result"
)
async def get_task_status(task_id: str):
    """
    Poll this endpoint with the task_id received from triggering endpoints
    to check the status and get the result when complete.
    """
    logger.info(f"Checking status for task ID: {task_id}")
    task_result = AsyncResult(task_id, app=celery_app)

    response_data = schemas.TaskStatusResponse(
        task_id=task_id,
        status=task_result.status,
        result=None,
        error=None
    )
    logger.debug(f"Initial task status for {task_id}: {task_result.status}")

    if task_result.successful():
        response_data.result = task_result.get()
        logger.info(f"Task {task_id} completed successfully.")
        # Avoid logging potentially large results unless necessary
        logger.debug(f"Task {task_id} result type: {type(response_data.result).__name__}")
    elif task_result.failed():
        try:
             # Celery stores exception info in the backend
             error_info = task_result.backend.get(task_result.id) # Fetch stored result/error
             # Sometimes the result itself contains the traceback if stored by the task failure logic
             if isinstance(error_info, Exception):
                 response_data.error = f"{type(error_info).__name__}: {error_info}"
             else:
                 # Try accessing traceback if available (depends on Celery config/backend)
                 response_data.error = f"Task failed. Traceback: {task_result.traceback or 'Not available'}"

             logger.error(f"Task {task_id} failed. Error info retrieved: {response_data.error[:500]}...") # Log truncated error
        except Exception as e:
             logger.exception(f"Failed to retrieve detailed error info for failed task {task_id}")
             response_data.error = f"Task failed, error details retrieval failed: {e}"
    elif task_result.status == 'PENDING':
        logger.debug(f"Task {task_id} is pending.")
        # Optional check if task ID is known (can be expensive)
        # meta = task_result.backend.get_task_meta(task_id)
        # if meta is None:
        #     logger.warning(f"Task ID {task_id} not found in backend.")
        #     raise HTTPException(status_code=404, detail="Task ID not found")
    elif task_result.status == 'STARTED':
         logger.debug(f"Task {task_id} has started.")
         # meta = task_result.info # Get intermediate metadata if task updates it
         # logger.debug(f"Task {task_id} metadata: {meta}")

    # Handle other states like RETRY, REVOKED if needed
    else:
         logger.debug(f"Task {task_id} in unhandled state: {task_result.status}")

    return response_data