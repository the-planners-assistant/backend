# app/tasks.py
import time
import random
import asyncio
from typing import List, Dict, Any, Optional # Added Optional
import logging # Import logging
import json # For potential JSON processing if needed later
import traceback

from app.celery_app import celery_app
from app.models import schemas
from app.llm_clients import get_llm_client, BaseLLMClient # Import factory and base class
from google.genai import types # Import SDK types for constructing content parts

logger = logging.getLogger(__name__) # Get logger instance

# Helper function to safely truncate strings for logging
def truncate_string(s: Optional[str], max_len: int = 100) -> Optional[str]:
    if s is None:
        return None
    return s[:max_len] + "..." if len(s) > max_len else s

# Hypothetical function containing the actual heavy lifting
async def _run_actual_complex_generation(report_input: schemas.ReportInput, task_id: str, aerial_photo_uri: Optional[str] = None, aerial_photo_mime_type: Optional[str] = None) -> dict:
    """Placeholder for the real time-consuming report generation logic using the reporting LLM."""
    logger.info(f"TASK [{task_id}]: Starting complex generation. Photo included: {'Yes' if aerial_photo_uri else 'No'}")
    logger.debug(f"TASK [{task_id}]: Input proposal (truncated): {truncate_string(report_input.proposal_text)}")
    if aerial_photo_uri:
        logger.debug(f"TASK [{task_id}]: Aerial photo URI: {aerial_photo_uri}, MimeType: {aerial_photo_mime_type}")

    # Simulate some initial data fetching or processing
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # --- Use the Reporting LLM ---
    proposal_summary = "Error generating summary"
    ai_explanation = "Error generating explanation"
    # Use mock data as fallback, replace with actual analysis results
    constraints_analysis_list = [{"id": "gb1", "name": "Green Belt", "status": "Present"}]
    policy_analysis_list = [{"id": "HOU1", "relevance_score": 0.8, "reasoning": "Relevant."}]

    try:
        logger.debug(f"TASK [{task_id}]: Getting reporting LLM client.")
        reporting_client = get_llm_client(client_type="reporting")
        logger.info(f"TASK [{task_id}]: Using reporting model: {reporting_client.model_name}")

        # --- Construct Prompt Content ---
        # Start with text parts
        prompt_parts: List[Any] = [
            f"Generate planning report sections for a development proposal at lat={report_input.lat}, lon={report_input.lon}.\n",
            f"Proposal Description: {report_input.proposal_text}\n\n"
        ]

        # Add aerial photo if available
        if aerial_photo_uri and aerial_photo_mime_type:
             logger.debug(f"TASK [{task_id}]: Adding aerial photo part to prompt contents.")
             # Ensure the file URI is valid and accessible by the model
             # Use types.Part.from_uri for files uploaded via File API
             prompt_parts.append(types.Part.from_uri(uri=aerial_photo_uri, mime_type=aerial_photo_mime_type))
             prompt_parts.append("\nAnalyze the aerial photo in the context of the proposal.\n") # Add instruction related to photo

        # --- Example LLM Calls ---
        # 1. Summarize Proposal (using potentially multimodal input)
        logger.debug(f"TASK [{task_id}]: Generating proposal summary.")
        # Add specific instruction for summary
        summary_instruction = "First, provide a concise summary of the development proposal described above (and shown in the image, if provided)."
        summary_contents = prompt_parts + [summary_instruction]

        summary_result = await reporting_client.generate_content(summary_contents, temperature=0.5)
        proposal_summary = summary_result if isinstance(summary_result, str) else "Summary Error (Type Mismatch)"
        logger.info(f"TASK [{task_id}]: Generated proposal summary (truncated): {truncate_string(proposal_summary)}")
        await asyncio.sleep(random.uniform(0.5, 1.0)) # Simulate work

        # 2. Generate AI Explanation
        logger.debug(f"TASK [{task_id}]: Generating AI explanation.")
        # Assume constraints/policies fetched and passed somehow, or use placeholders
        explanation_prompt_parts = prompt_parts + [ # Reuse initial context + photo if available
             "\nNow, generate a concise explanation of the key planning considerations for the proposal, considering the following constraints and policies:\n",
             f"Constraints:\n" + "\n".join([f"- {c['name']} ({c['status']})" for c in constraints_analysis_list]) + "\n",
             f"Relevant Policies:\n" + "\n".join([f"- {p['id']}: Score {p['relevance_score']}" for p in policy_analysis_list]) + "\n",
             "Focus on potential conflicts and opportunities highlighted by the proposal, constraints, policies (and aerial photo, if provided)."
        ]
        explanation_result = await reporting_client.generate_content(explanation_prompt_parts, temperature=0.6)
        ai_explanation = explanation_result if isinstance(explanation_result, str) else "Explanation Error (Type Mismatch)"
        logger.info(f"TASK [{task_id}]: Generated AI explanation (truncated): {truncate_string(ai_explanation)}")
        await asyncio.sleep(random.uniform(0.5, 1.0)) # Simulate work

        # --- TODO: Add actual constraint/policy analysis logic ---


    except Exception as e:
         logger.exception(f"TASK [{task_id}]: Error during LLM interaction.")
         # Keep previously set error messages or placeholders

    # Structure report dictionary
    report_dict = {
         "request": report_input.model_dump(),
         "proposal_summary": proposal_summary,
         "constraints_analysis": constraints_analysis_list, # Replace with actual analysis results
         "ai_explanation": ai_explanation,
         "relevant_policies": policy_analysis_list # Replace with actual analysis results
     }
    logger.info(f"TASK [{task_id}]: Finished complex generation logic.")
    return report_dict


@celery_app.task(bind=True, name="generate_report_task")
def generate_report_task(self, report_input_dict: dict) -> dict:
    """
    Celery task to generate the planning report asynchronously.
    Accepts and returns serializable dicts. Can handle optional aerial photo info.
    """
    task_id = self.request.id or "unknown_task"
    logger.info(f"TASK [{task_id}]: Received report generation request.")
    logger.debug(f"TASK [{task_id}]: Raw input dict keys: {list(report_input_dict.keys())}")

    # Extract potential aerial photo info BEFORE creating the base ReportInput model
    aerial_photo_uri = report_input_dict.pop("aerial_photo_uri", None)
    aerial_photo_mime_type = report_input_dict.pop("aerial_photo_mime_type", None)
    # aerial_photo_name = report_input_dict.pop("aerial_photo_name", None) # Optional: Use if needed

    try:
        # Create the Pydantic model from the remaining dict keys
        report_input = schemas.ReportInput(**report_input_dict)
        logger.info(f"TASK [{task_id}]: Parsed input. Proposal (truncated): {truncate_string(report_input.proposal_text)}. Photo URI present: {'Yes' if aerial_photo_uri else 'No'}")

        # Run the async generation logic using asyncio.run()
        # Pass extracted photo info to the generation function
        result_data = asyncio.run(
            _run_actual_complex_generation(
                report_input=report_input,
                task_id=task_id,
                aerial_photo_uri=aerial_photo_uri,
                aerial_photo_mime_type=aerial_photo_mime_type
            )
        )

        logger.info(f"TASK [{task_id}]: Report generation logic completed successfully.")
        return result_data
    except Exception as e:
        logger.exception(f"TASK [{task_id}]: Unhandled error during task execution.")
        # Update task state with error details
        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(e).__name__, 'exc_message': str(e), 'traceback': traceback.format_exc()} # Include traceback if possible
        )
        # Reraise exception for Celery to record failure status
        raise # Reraises the caught exception
    finally:
        # --- Optional: Clean up uploaded file ---
        # Requires passing file name and using the client again
        # Be careful with error handling here
        # if aerial_photo_name:
        #     try:
        #         logger.warning(f"TASK [{task_id}]: Attempting to delete uploaded file: {aerial_photo_name}")
        #         # Need to get client instance again
        #         # file_cleanup_client = get_llm_client(...)
        #         # await file_cleanup_client.delete_file(name=aerial_photo_name) # Assumes delete_file method exists
        #     except Exception as cleanup_err:
        #         logger.error(f"TASK [{task_id}]: Failed to delete uploaded file {aerial_photo_name}: {cleanup_err}")
        logger.debug(f"TASK [{task_id}]: generate_report_task finished.")