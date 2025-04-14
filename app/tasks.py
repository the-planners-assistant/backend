# app/tasks.py
import time
import random
import asyncio
from typing import List, Dict, Any, Optional, Union
import logging
import json
from pathlib import Path

from app.celery_app import celery_app
from app.models import schemas # Import all schemas needed
from app.llm_clients import get_llm_client, BaseLLMClient
# google.genai.types not needed for Part creation
from pydantic import ValidationError, TypeAdapter # Keep for validation

try:
    from app.services.constraints_service import load_prompt_template
except ImportError:
    PROMPT_DIR_TASK = Path(__file__).parent / "prompts"
    logger_tp = logging.getLogger(__name__ + ".load_prompt_template")
    def load_prompt_template(template_name: str) -> str:
        filepath = PROMPT_DIR_TASK / template_name
        logger_tp.debug(f"Attempting to load prompt template from: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f: return f.read()
        except Exception as e:
            logger_tp.error(f"Task Error loading prompt {filepath}: {e}")
            raise

logger = logging.getLogger(__name__)

def truncate_string(s: Optional[str], max_len: int = 100) -> Optional[str]:
    if s is None: return None
    return s[:max_len] + "..." if len(s) > max_len else s

async def run_report_generation(task_input: schemas.ReportTaskInput, task_id: str) -> dict:
    """
    Performs report generation using reporting LLM, requesting JSON mime type output
    and manually parsing/validating it against ReportData schema.
    """
    logger.info(f"TASK [{task_id}]: Starting report generation.")
    logger.debug(f"TASK [{task_id}]: Address: {task_input.formatted_address}")
    logger.debug(f"TASK [{task_id}]: Aerial URI: {task_input.aerial_photo_uri}")
    logger.debug(f"TASK [{task_id}]: Street View URI: {task_input.street_view_photo_uri}")

    error_report_data = schemas.ReportData( request=task_input.request, proposal_summary="Error: Failed.", constraints_analysis=[], relevant_policies=[], ai_explanation="Error: Initial task failure.")
    final_report_dict = error_report_data.model_dump()

    try:
        logger.debug(f"TASK [{task_id}]: Getting reporting LLM client.")
        reporting_client = get_llm_client(client_type="reporting")
        logger.info(f"TASK [{task_id}]: Using reporting model: {reporting_client.model_name}")

        logger.debug(f"TASK [{task_id}]: Loading report generation prompt template.")
        prompt_template = load_prompt_template("generate_report.txt") # Use prompt asking for specific JSON structure

        # Prepare Prompt Context (includes image URIs in text)
        constraints_json_string = json.dumps([c.model_dump() for c in task_input.ranked_constraints], indent=2)
        policies_json_string = json.dumps([p.model_dump() for p in task_input.ranked_policies], indent=2)
        aerial_photo_context_str = f"\n- Aerial Photo URI: {task_input.aerial_photo_uri}" if task_input.aerial_photo_uri else ""
        street_view_photo_context_str = f"\n- Street View URI: {task_input.street_view_photo_uri}" if task_input.street_view_photo_uri else ""
        proposal_text_for_prompt = task_input.request.proposal_text or ""
        prompt_context = { "latitude": task_input.request.lat, "longitude": task_input.request.lon, "formatted_address": task_input.formatted_address or "Not Available", "proposal_text": proposal_text_for_prompt, "constraints_json": constraints_json_string, "policies_json": policies_json_string, "aerial_photo_context": aerial_photo_context_str, "street_view_photo_context": street_view_photo_context_str }
        final_prompt_text = prompt_template.format(**prompt_context)
        logger.debug(f"TASK [{task_id}]: Final report prompt length: {len(final_prompt_text)}")

        # Prepare Content List (TEXT ONLY - URIs are in the text prompt)
        llm_contents: list[str] = [final_prompt_text]

        # --- Call LLM requesting JSON mime type, NO schema enforcement by API ---
        logger.info(f"TASK [{task_id}]: Calling reporting LLM for report components (manual parse)...")
        llm_output_dict = await reporting_client.generate_content(
            prompt=llm_contents,
            stream=False,
            output_json=True, # Request JSON mime type + trigger manual parse in client
            # response_schema=... REMOVED
            temperature=0.6
        )

        # --- Process Response (should be dictionary) ---
        if not isinstance(llm_output_dict, dict):
             logger.error(f"TASK [{task_id}]: Reporting LLM did not return a JSON dictionary. Type: {type(llm_output_dict)}")
             raise ValueError("LLM response was not a valid JSON dictionary.")
        else:
             logger.info(f"TASK [{task_id}]: Successfully received and parsed JSON dictionary from LLM.")
             # --- Manually Validate and Construct ReportData ---
             logger.debug("Manually validating LLM output dictionary against ReportData schema...")
             try:
                  # Validate the entire dict against the final ReportData schema
                  final_report_obj = schemas.ReportData(**llm_output_dict)
                  # Convert the validated object to dict for Celery/JSON result
                  final_report_dict = final_report_obj.model_dump()
                  logger.info(f"TASK [{task_id}]: Successfully validated LLM output and constructed ReportData.")

             except ValidationError as e:
                  logger.error(f"TASK [{task_id}]: Pydantic validation failed for LLM output dictionary: {e}", exc_info=True)
                  logger.error(f"TASK [{task_id}]: LLM Output causing validation error: {llm_output_dict}")
                  # Use default error dict but update explanation
                  final_report_dict['ai_explanation'] = f"Error: LLM output failed validation against ReportData schema ({e})."
                  # Keep request field from original input
                  final_report_dict['request'] = task_input.request.model_dump()
             except Exception as const_err:
                  logger.exception(f"TASK [{task_id}]: Error constructing final ReportData object from dict.")
                  # Use default error dict but update explanation
                  final_report_dict['ai_explanation'] = f"Error: Failed during final report construction ({type(const_err).__name__})."
                  final_report_dict['request'] = task_input.request.model_dump()

    # --- Outer Error Handling ---
    except FileNotFoundError as fnf_err:
        logger.exception(f"TASK [{task_id}]: Prompt template file not found.")
        final_report_dict['ai_explanation'] = f"Error: Report generation prompt template not found ({fnf_err})."
        final_report_dict['request'] = task_input.request.model_dump()
    except ValueError as ve: # Catch errors from LLM call or manual JSON parse
        logger.exception(f"TASK [{task_id}]: Value error during report generation LLM call or parsing.")
        # Include the ValueError message in the explanation
        final_report_dict['ai_explanation'] = f"Error: Failed during LLM call or response parsing ({ve})."
        final_report_dict['request'] = task_input.request.model_dump()
    except Exception as e:
        logger.exception(f"TASK [{task_id}]: Unexpected error during report generation.")
        final_report_dict['ai_explanation'] = f"Error: An unexpected error occurred ({type(e).__name__})."
        final_report_dict['request'] = task_input.request.model_dump()


    logger.info(f"TASK [{task_id}]: Report generation finished.")
    return final_report_dict # Return the dictionary


@celery_app.task(bind=True, name="generate_report_task")
def generate_report_task(self, task_input_dict: dict) -> dict:
    # (Wrapper function remains the same)
    task_id = self.request.id or "unknown_task"
    logger.info(f"TASK [{task_id}]: Celery task received request.")
    logger.debug(f"TASK [{task_id}]: Raw input dict keys: {list(task_input_dict.keys())}")
    try:
        task_input = schemas.ReportTaskInput(**task_input_dict)
        logger.debug(f"TASK [{task_id}]: Successfully parsed ReportTaskInput.")
        result_data = asyncio.run(run_report_generation(task_input, task_id))
        logger.info(f"TASK [{task_id}]: Celery task completed successfully.")
        return result_data
    except Exception as e:
        logger.exception(f"TASK [{task_id}]: Unhandled error during task execution.")
        import traceback
        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(e).__name__, 'exc_message': str(e), 'traceback': traceback.format_exc()}
        )
        raise