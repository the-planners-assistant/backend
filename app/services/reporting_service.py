# app/services/reporting_service.py
from app.models import schemas
from app.tasks import generate_report_task # Import the celery task
from celery.result import AsyncResult # To check results within service if needed

async def trigger_report_generation(report_input: schemas.ReportInput) -> str:
    """
    Service function to trigger the asynchronous report generation task.
    Returns the task ID.
    """
    print(f"SERVICE: Triggering report generation task for {report_input.model_dump_json(indent=2)}") # Log input
    # Send task to the queue. Pass data as a serializable dict using .model_dump()
    # Ensure all data within report_input is JSON-serializable
    task = generate_report_task.delay(report_input.model_dump())
    print(f"SERVICE: Task {task.id} enqueued.")
    return task.id # Return the task ID to the caller (router)

# The actual long-running logic (_run_actual_complex_generation) now resides
# conceptually within or is called by the Celery task defined in app/tasks.py