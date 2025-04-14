# app/llm_clients/gemini_client.py
# (Using the version that requests JSON mime type but does NOT use response_schema)
import google.genai as genai
from google.genai import types
from google.genai.client import Client as GenAIClient
from pydantic import BaseModel, ValidationError, Field
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Type
import asyncio
import json
from io import BytesIO
import logging

from .base import BaseLLMClient, LLMInputType, LLMOutputType
from app.core.config import settings

logger = logging.getLogger(__name__)

# Pydantic model for Rerank validation (still used manually)
class RerankResponse(BaseModel):
     ranked_ids: List[str] = Field(..., description="List of item IDs in order of relevance")

class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        logger.info(f"Initializing GeminiClient with model: {model_name}")
        try:
             self.client = GenAIClient(api_key=api_key)
             logger.debug("Gemini Client initialized.")
        except Exception as e:
             logger.critical(f"Error initializing Gemini Client: {e}", exc_info=True)
             raise ValueError("Gemini API key not configured or invalid.") from e
        self.model_name = model_name

    async def upload_file(
        self,
        file_data: BytesIO,
        mime_type: str,
        display_name: Optional[str] = None
    ) -> types.File:
         logger.info(f"Uploading file. MimeType: {mime_type}, DisplayName: {display_name}")
         try:
             file_data.seek(0)
             uploaded_file = await asyncio.to_thread(
                 self.client.files.upload,
                 file=file_data,
                 config={"mime_type": mime_type, "display_name": display_name}
             )
             logger.info(f"File uploaded successfully: Name={uploaded_file.name}, URI={uploaded_file.uri}, State={uploaded_file.state}")
             return uploaded_file
         except Exception as e:
             logger.error(f"Error uploading file to Gemini: {e}", exc_info=True)
             raise

    async def _generate_content_internal(
        self,
        contents: Union[str, list],
        stream: bool = False,
        # response_schema parameter REMOVED
        output_json: bool = False, # Keep flag to request JSON mime type
        generation_config_dict: Optional[Dict[str, Any]] = None,
        safety_settings_list: Optional[List[Dict[str, str]]] = None,
    ) -> Union[LLMOutputType, AsyncGenerator[types.GenerateContentResponse, None]]:
        """Internal helper, passes config as dict, uses client.aio. NO response_schema."""
        logger.debug(f"Entering _generate_content_internal. Stream: {stream}, Request JSON Output: {output_json}")
        final_config_dict: Optional[Dict[str, Any]] = None
        try:
            config_dict = generation_config_dict.copy() if generation_config_dict else {}
            needs_config = bool(config_dict)

            if safety_settings_list:
                 config_dict['safety_settings'] = safety_settings_list
                 needs_config = True
                 logger.debug(f"Adding safety settings to config dict: {safety_settings_list}")

            if output_json:
                 logger.debug(f"Requesting JSON output mime type for model {self.model_name}")
                 config_dict['response_mime_type'] = "application/json"
                 # REMOVED: config_dict['response_schema'] = response_schema
                 needs_config = True

            # Explicitly disable AFC if no tools specified (safety)
            if 'tools' not in config_dict and 'tool_config' not in config_dict:
                 logger.debug("Explicitly disabling automatic_function_calling via config dict.")
                 config_dict['automatic_function_calling'] = {'disable': True}
                 needs_config = True

            if needs_config:
                 final_config_dict = config_dict
                 logger.debug(f"Final config dictionary to be passed: {final_config_dict}")
            else:
                 logger.debug("No specific generation config provided, passing config=None.")
                 final_config_dict = None

            logger.debug(f"Using model name directly: {self.model_name}")

            logger.debug("Calling client.aio.models.generate_content...")
            response_source = self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=final_config_dict
            )

            if stream:
                if output_json:
                    logger.warning("Streaming JSON output requested. Caller needs to handle chunk parsing and assembly.")
                logger.debug("Returning async generator for streaming.")
                return response_source # type: ignore
            else:
                logger.debug("Awaiting full response for non-streaming request.")
                response = await response_source
                logger.debug("Received full response from generate_content.")

                if not getattr(response, 'candidates', None):
                    feedback = getattr(response, 'prompt_feedback', getattr(response, 'error', None))
                    logger.error(f"Gemini API returned no candidates. Feedback/Error: {feedback}")
                    raise ValueError(f"Gemini API returned no candidates. Feedback/Error: {feedback}")

                try:
                    response_text = response.text
                except ValueError as e:
                    feedback = getattr(response, 'prompt_feedback', None)
                    logger.error(f"Could not access response text (potentially blocked content): {e}. Feedback: {feedback}")
                    raise ValueError(f"Could not access response text. Feedback: {feedback}") from e

                # --- Manual JSON parsing if requested ---
                if output_json:
                    logger.debug("Attempting to parse JSON response manually.")
                    try:
                        parsed_json = json.loads(response_text)
                        logger.debug("Successfully parsed JSON response manually.")
                        return parsed_json # Return the parsed dict/list
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Manual JSON parsing failed: {json_err}. Raw text (truncated): {response_text[:500]}...")
                        raise ValueError(f"LLM did not return valid JSON for manual parsing: {json_err}") from json_err
                else:
                    logger.debug("Returning plain text response.")
                    return response_text

        except Exception as e:
             logger.exception(f"Error calling Gemini generate_content for model {self.model_name}")
             raise

    async def generate_content(
        self,
        prompt: LLMInputType,
        stream: bool = False,
        # response_schema parameter removed
        output_json: bool = False, # Keep flag to control manual parsing
        **kwargs
    ) -> Union[LLMOutputType, AsyncGenerator[types.GenerateContentResponse, None]]:
        """
        Generates content. If output_json is True, requests JSON mime type and
        attempts manual JSON parsing of the result (unless streaming).
        """
        # (Wrapper method logic remains the same)
        logger.debug(f"generate_content called. Stream: {stream}, Output JSON: {output_json}")
        if isinstance(prompt, str): contents = [prompt]
        elif isinstance(prompt, list): contents = prompt
        else: raise TypeError("Prompt must be a string or a list.")

        valid_config_keys = set(types.GenerationConfig.__annotations__.keys()) | {'automatic_function_calling', 'tool_config', 'tools'}
        gen_config_dict = {k: v for k, v in kwargs.items() if k in valid_config_keys and k not in ['safety_settings', 'response_schema']}
        safety_settings_list = kwargs.get("safety_settings")
        if 'automatic_function_calling' in kwargs: gen_config_dict['automatic_function_calling'] = kwargs['automatic_function_calling']
        if 'tool_config' in kwargs: gen_config_dict['tool_config'] = kwargs['tool_config']

        logger.debug(f"Generation Config dict (from kwargs): {gen_config_dict}")
        logger.debug(f"Safety Settings list (from kwargs): {safety_settings_list}")

        return await self._generate_content_internal(
            contents=contents,
            stream=stream,
            output_json=output_json,
            # response_schema=None, # No longer passing schema
            generation_config_dict=gen_config_dict,
            safety_settings_list=safety_settings_list
        )

    async def rerank_items(
        self,
        items: List[Dict[str, Any]],
        prompt_template: str,
        prompt_context: Dict[str, Any],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Re-ranks items using a prompt template and context.
        Requests JSON output and manually parses/validates it.
        """
        # (Rerank items logic uses manual parse/validate)
        logger.info(f"Reranking {len(items)} items using provided template (manual JSON parse).")
        logger.debug(f"Prompt context: {prompt_context}")
        items_json_string = json.dumps([{"id": str(item.get('id')), "name": item.get('name'), "type": item.get('type'), "description": item.get('description')} for item in items], indent=2)
        prompt_context_with_items = prompt_context.copy(); prompt_context_with_items['items_json'] = items_json_string
        try:
             final_prompt = prompt_template.format(**prompt_context_with_items)
             logger.debug(f"Formatted rerank prompt (truncated): {final_prompt[:300]}...")
        except Exception as format_err:
             logger.error(f"Error formatting prompt template: {format_err}", exc_info=True)
             raise ValueError("Failed to format prompt template") from format_err

        item_map = {str(item.get('id')): item for item in items}

        try:
            gen_kwargs = kwargs.copy(); gen_kwargs.setdefault('temperature', 0.1)
            logger.debug(f"Calling generate_content for reranking (Requesting JSON output). Kwargs: {gen_kwargs}")

            json_response = await self.generate_content(
                final_prompt, stream=False, output_json=True, **gen_kwargs
            )

            if not isinstance(json_response, dict):
                 logger.error(f"Reranking expected dict response from manual parse, got {type(json_response)}")
                 raise TypeError(f"Expected dict response from manual parse, got {type(json_response)}")

            logger.debug(f"Received and manually parsed JSON response for reranking: {json_response}")

            # Manually Validate with Pydantic
            try:
                 validated_response = RerankResponse(**json_response)
                 ranked_ids = validated_response.ranked_ids
                 logger.info(f"Successfully MANUALLY validated {len(ranked_ids)} ranked IDs.")
                 logger.debug(f"Validated ranked IDs: {ranked_ids}")
            except ValidationError as e:
                 logger.error(f"MANUAL Pydantic validation failed for rerank response: {e}. Received JSON: {json_response}", exc_info=True)
                 return items

            # Reconstruct ranked_items list
            ranked_items = []
            processed_ids = set()
            for item_id in ranked_ids:
                 if item_id in item_map and item_id not in processed_ids:
                     ranked_items.append(item_map[item_id]); processed_ids.add(item_id)
                 else: logger.warning(f"Reranking JSON included unknown or duplicate ID from LLM: {item_id}")
            logger.debug(f"Final ranked item count: {len(ranked_items)}")
            return ranked_items

        except ValueError as ve: logger.error(f"Value error during reranking LLM call or manual parsing: {ve}", exc_info=False); return items
        except Exception as e: logger.exception("Unexpected error during Gemini JSON re-ranking execution"); return items