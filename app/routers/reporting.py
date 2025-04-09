# app/routers/reporting.py
from fastapi import APIRouter, HTTPException, status

from app.models import schemas # Import specific response model too
from app.services.reporting_service import trigger_report_generation
from app.core.config import settings

router = APIRouter(
    tags=["Reporting"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/generate_report", # Endpoint path
    response_model=schemas.AsyncTaskResponse, # Respond with task info
    status_code=status.HTTP_202_ACCEPTED, # Use 202 Accepted status code
    summary="Trigger AI Planning Report Generation",
    description="Triggers asynchronous generation of an AI-assisted planning report based on location and proposal details. Returns a task ID for status polling."
)
async def trigger_ai_report(report_input: schemas.ReportInput):
    """
    API endpoint to trigger asynchronous report generation.
    Returns a task ID for polling status/results.
    - **report_input**: Includes location and optional proposal text.
    """
    try:
        print(f"ROUTER: Received trigger report request for {report_input.model_dump_json()}")
        # Call service to enqueue the task
        task_id = await trigger_report_generation(report_input)

        print(f"ROUTER: Returning task ID {task_id}")
        return schemas.AsyncTaskResponse(task_id=task_id, status="PENDING")
    except Exception as e:
        print(f"ROUTER: Error triggering report generation: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while triggering report.")

# Add other reporting endpoints if needed