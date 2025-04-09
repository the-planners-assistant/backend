# app/tasks.py
import time
import random
from app.celery_app import celery_app
from app.models import schemas # Import necessary schemas
# Import the actual logic function if separated, or put logic here
# from app.services import reporting_service # Example: If core logic remains in service

# Hypothetical function containing the actual heavy lifting
# This might live in reporting_service.py or a dedicated analysis module
def _run_actual_complex_generation(report_input: schemas.ReportInput) -> dict:
    """Placeholder for the real time-consuming report generation logic."""
    time.sleep(random.uniform(5.0, 10.0)) # Simulate long work
    # Create mock report data (as done in the service before)
    constraints_analysis_list = [{"id": "gb1", "name": "Green Belt", "status": "Present"}] # Example
    policy_analysis_list = [{"id": "HOU1", "relevance_score": 0.8, "reasoning": "Relevant."}] # Example
    ai_explanation = "Async Mock AI Analysis: Processing complete via Celery."
    proposal_summary = f"Async Mock Summary for: {report_input.proposal_text or 'N/A'}"

    # Structure as a dict matching ReportData fields (or close enough for JSON)
    mock_report_dict = {
         "request": report_input.model_dump(), # Use model_dump for serialization
         "proposal_summary": proposal_summary,
         "constraints_analysis": constraints_analysis_list,
         "ai_explanation": ai_explanation,
         "relevant_policies": policy_analysis_list
     }
    return mock_report_dict


@celery_app.task(bind=True, name="generate_report_task") # bind=True allows access 'self', name provides explicit task name
def generate_report_task(self, report_input_dict: dict) -> dict:
    """
    Celery task to generate the planning report asynchronously.
    Accepts and returns serializable dicts.
    'self' refers to the task instance (request context).
    """
    try:
        task_id = self.request.id
        print(f"TASK [{task_id}]: Started report generation.")
        # Re-instantiate Pydantic model from dict for type safety within task
        report_input = schemas.ReportInput(**report_input_dict)

        # Call the function containing the actual long-running logic
        result_data = _run_actual_complex_generation(report_input)

        print(f"TASK [{task_id}]: Finished successfully.")
        # Return results as a dict (Celery serializes this)
        return result_data
    except Exception as e:
        task_id = self.request.id or "unknown"
        print(f"TASK [{task_id}]: Failed - {type(e).__name__}: {e}")
        # Update task state with error details for polling endpoint
        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(e).__name__, 'exc_message': str(e)}
        )
        # You might want to raise a specific Celery exception type if needed
        # but raising the original often works for tracking.
        raise # Reraise exception for Celery to record failure status

# Add other tasks here (e.g., analyse_consultation_task, run_scenario_task)