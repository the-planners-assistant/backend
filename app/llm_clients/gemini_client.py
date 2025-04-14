# app/llm_clients/gemini_client.py
import google.genai as genai # Correct SDK import
from google.genai import types
from google.genai.client import Client as GenAIClient # Alias to avoid confusion
from pydantic import BaseModel, ValidationError, Field
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Type
import asyncio
import json
from io import BytesIO
import logging # Import logging

from .base import BaseLLMClient, LLMInputType, LLMOutputType
from app.core.config import settings

logger = logging.getLogger(__name__) # Get logger instance

# --- Optional: Pydantic model for expected Rerank response ---
class RerankResponse(BaseModel):
     ranked_ids: List[str] = Field(..., description="List of item IDs in order of relevance")

class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        logger.info(f"Initializing GeminiClient with model: {model_name}")
        try:
             # Attempt to initialize. SDK handles env var lookup if api_key is None.
             self.client = GenAIClient(api_key=api_key)
             # Optional: Verify connection/auth if possible (e.g., list models)
             # models = list(self.client.models.list()) # Synchronous, use asyncio.to_thread if needed
             # logger.debug(f"Successfully initialized Gemini Client. Found {len(models)} models.")
             logger.debug("Gemini Client initialized.")
        except Exception as e:
             logger.critical(f"Error initializing Gemini Client: {e}", exc_info=True) # Critical for client init failure
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
             file_data.seek(0) # Ensure stream is at the beginning
             # Run synchronous SDK call in thread pool
             uploaded_file = await asyncio.to_thread(
                 self.client.files.upload,
                 file=file_data,
                 config={"mime_type": mime_type, "display_name": display_name}
             )
             logger.info(f"File uploaded successfully: Name={uploaded_file.name}, URI={uploaded_file.uri}, State={uploaded_file.state}")
             # Optional: Add polling logic here if needed
             # ...
             return uploaded_file
         except Exception as e:
             logger.error(f"Error uploading file to Gemini: {e}", exc_info=True)
             raise

    async def _generate_content_internal(
        self,
        contents: Union[str, list],
        stream: bool = False,
        output_json: bool = False,
        generation_config_dict: Optional[Dict[str, Any]] = None,
        safety_settings_list: Optional[List[Dict[str, str]]] = None
    ) -> Union[LLMOutputType, AsyncGenerator[types.GenerateContentResponse, None]]:
        """Internal helper for generation, handles config creation."""
        logger.debug(f"Entering _generate_content_internal. Stream: {stream}, JSON: {output_json}")
        try:
            gen_config_obj = types.GenerationConfig(**generation_config_dict) if generation_config_dict else types.GenerationConfig()
            safety_settings_obj = [types.SafetySetting(**s) for s in safety_settings_list] if safety_settings_list else None

            if output_json:
                 logger.debug(f"Requesting JSON output (response_mime_type='application/json') for model {self.model_name}")
                 gen_config_obj.response_mime_type = "application/json"

            model_to_use = self.client.models.get(self.model_name)
            logger.debug(f"Using model: {self.model_name}")

            if stream:
                 if output_json:
                      logger.warning("Streaming JSON output requested. Manual reassembly of chunks might be needed by the caller.")
                 logger.debug("Calling generate_content_async (stream=True)...")
                 return await model_to_use.generate_content_async(
                     contents=contents,
                     generation_config=gen_config_obj,
                     safety_settings=safety_settings_obj,
                     stream=True
                 )
            else:
                 logger.debug("Calling generate_content_async (stream=False)...")
                 response = await model_to_use.generate_content_async(
                     contents=contents,
                     generation_config=gen_config_obj,
                     safety_settings=safety_settings_obj,
                     stream=False
                 )
                 logger.debug("Received response from generate_content_async.")

                 if not response.candidates:
                      feedback = getattr(response, 'prompt_feedback', None)
                      logger.error(f"Gemini API returned no candidates. Feedback: {feedback}")
                      raise ValueError(f"Gemini API returned no candidates. Feedback: {feedback}")

                 response_text = response.text # Might be empty if blocked

                 if output_json:
                      logger.debug("Attempting to parse JSON response.")
                      try:
                           parsed_json = json.loads(response_text)
                           logger.debug("Successfully parsed JSON response from LLM.")
                           return parsed_json
                      except json.JSONDecodeError as json_err:
                           logger.error(f"Failed decoding JSON response: {json_err}. Raw text (truncated): {response_text[:500]}...")
                           raise ValueError(f"LLM did not return valid JSON: {json_err}") from json_err
                 else:
                      logger.debug("Returning plain text response.")
                      return response_text

        except Exception as e:
            # Log specific exceptions if possible (e.g., BlockedPromptError, StopCandidateException from SDK)
            logger.exception(f"Error calling Gemini generate_content for model {self.model_name}")
            raise

    async def generate_content(
        self,
        prompt: LLMInputType,
        stream: bool = False,
        output_json: bool = False,
        **kwargs
    ) -> Union[LLMOutputType, AsyncGenerator[types.GenerateContentResponse, None]]:
        """Generates content, handling input formatting, streaming, and JSON output request."""
        logger.debug(f"generate_content called. Stream: {stream}, JSON: {output_json}")
        # Basic input formatting
        if isinstance(prompt, str):
             contents = [prompt]
        elif isinstance(prompt, list):
             contents = prompt
        else:
             logger.error(f"Invalid prompt type received: {type(prompt)}")
             raise TypeError("Prompt must be a string or a list.")

        # Extract generation config and safety settings from kwargs
        gen_config_dict = {k: v for k, v in kwargs.items() if k in types.GenerationConfig.__annotations__}
        safety_settings_list = kwargs.get("safety_settings")
        logger.debug(f"Generation Config kwargs: {gen_config_dict}")
        logger.debug(f"Safety Settings list: {safety_settings_list}")

        return await self._generate_content_internal(
            contents=contents,
            stream=stream,
            output_json=output_json,
            generation_config_dict=gen_config_dict,
            safety_settings_list=safety_settings_list
        )

    async def rerank_items(
        self,
        items: List[Dict[str, Any]],
        context: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Re-ranks items using the Gemini model, expecting a JSON list of IDs."""
        logger.info(f"Reranking {len(items)} items.")
        logger.debug(f"Reranking context (truncated): {context[:100]}...")

        # --- Construct Prompt for JSON output ---
        prompt = f"Context: {context}\n\n"
        # ... (rest of prompt definition as before) ...
        prompt += "Please re-rank the following items based ONLY on their relevance to the context provided above. \n"
        prompt += "Output a JSON object containing a single key 'ranked_ids'. The value of 'ranked_ids' must be a JSON array of strings, where each string is the ID of an item from the input list. \n"
        prompt += "Order the IDs in the array from the most relevant item to the least relevant item based on the context. \n"
        prompt += "Include ONLY the IDs of items you consider relevant. If no items are relevant, return an empty array: { \"ranked_ids\": [] }. \n"
        prompt += "Do NOT include explanations, justifications, or any text outside the JSON structure.\n\n"
        prompt += "Input Items:\n"

        item_map = {}
        prompt_items_log = []
        for i, item in enumerate(items):
            item_id = str(item.get('id', f'item_{i}'))
            item_map[item_id] = item
            name = item.get('name', '')
            desc = item.get('description', '')
            item_text = f"{{ \"id\": \"{item_id}\", \"name\": \"{name}\", \"description\": \"{desc}\" }}"
            prompt += f"- {item_text}\n"
            if i < 5: # Log first few items for debugging
                 prompt_items_log.append(item_text)
        if len(items) > 5:
             prompt_items_log.append("...")
        logger.debug(f"Items included in rerank prompt (sample): {prompt_items_log}")

        prompt += "\nOutput JSON:"

        try:
            kwargs.setdefault('temperature', 0.1) # Low temp for deterministic ranking
            logger.debug(f"Calling generate_content for reranking (JSON requested). Config: {kwargs}")
            json_response = await self.generate_content(prompt, output_json=True, **kwargs)

            if not isinstance(json_response, dict):
                 logger.error(f"Reranking expected dict JSON response, got {type(json_response)}")
                 raise TypeError(f"Expected dict response for JSON reranking, got {type(json_response)}")

            logger.debug(f"Received JSON response for reranking: {json_response}")

            # --- Validate with Pydantic ---
            try:
                 validated_response = RerankResponse(**json_response)
                 ranked_ids = validated_response.ranked_ids
                 logger.info(f"Successfully parsed and validated {len(ranked_ids)} ranked IDs.")
                 logger.debug(f"Validated ranked IDs: {ranked_ids}")
            except ValidationError as e:
                 logger.error(f"Pydantic validation failed for rerank response: {e}. Received JSON: {json_response}", exc_info=True)
                 return items # Fallback to original order on validation failure

            # Reconstruct the list in the new order based on validated IDs
            ranked_items = []
            processed_ids = set()
            for item_id in ranked_ids:
                 if item_id in item_map and item_id not in processed_ids:
                     ranked_items.append(item_map[item_id])
                     processed_ids.add(item_id)
                 else:
                      logger.warning(f"Reranking JSON included unknown or duplicate ID: {item_id}")

            logger.debug(f"Final ranked item count: {len(ranked_items)}")
            return ranked_items

        except Exception as e:
            logger.exception("Error during Gemini JSON re-ranking")
            return items # Fallback to original order on error