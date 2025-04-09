# app/routers/tasks_router.py
from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult
from app.celery_app import celery_app # Import your configured celery app
from app.models import schemas # Import specific response model
from app.core.config import settings
from typing import Any

router = APIRouter(
    tags=["Task Status"],
    responses={404: {"description": "Task not found"}},
)

@router.get(
    "/tasks/{task_id}/status", # Path relative to global prefix
    response_model=schemas.TaskStatusResponse,
    summary="Get Background Task Status and Result"
)
async def get_task_status(task_id: str):
    """
    Poll this endpoint with the task_id received from triggering endpoints
    to check the status and get the result when complete.
    """
    print(f"ROUTER: Checking status for task {task_id}")
    task_result = AsyncResult(task_id, app=celery_app)

    response_data = schemas.TaskStatusResponse(
        task_id=task_id,
        status=task_result.status,
        result=None, # Default to None
        error=None   # Default to None
    )

    if task_result.successful():
        response_data.result = task_result.get() # Get the result (likely the report dict)
        print(f"ROUTER: Task {task_id} successful.")
    elif task_result.failed():
        # Get the exception details Celery stored in the backend
        # task_result.backend.get raises exceptions on failure by default
        try:
             # This might fetch the traceback string depending on backend/config
             error_info = task_result.backend.get(task_result.id)
             response_data.error = str(error_info)
        except Exception as e:
             response_data.error = f"Failed to retrieve detailed error: {e}"
             # Log the traceback if possible here
             # print(task_result.traceback) # May or may not be available
        print(f"ROUTER: Task {task_id} failed. Error: {response_data.error}")
    elif task_result.status == 'PENDING':
        print(f"ROUTER: Task {task_id} is pending.")
        # Optionally check if task ID is even known to the backend
        # if task_result.backend.get_task_meta(task_id) is None:
        #     raise HTTPException(status_code=404, detail="Task ID not found")
    elif task_result.status == 'STARTED':
         print(f"ROUTER: Task {task_id} has started.")
         # You could potentially get intermediate metadata if the task updates it
         # meta = task_result.info
         # response_data['meta'] = meta # If TaskStatusResponse had a meta field

    # Handle other states like RETRY, REVOKED if needed

    return response_data