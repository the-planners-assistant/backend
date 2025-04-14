# app/llm_clients/__init__.py
from typing import Optional, Dict, Any
import logging # Import logging
from app.core.config import settings
from .base import BaseLLMClient
from .gemini_client import GeminiClient
# Import other clients like OpenAIClient if you add them later
# from .openai_client import OpenAIClient

logger = logging.getLogger(__name__) # Get logger instance

# Simple cache for client instances
_clients: Dict[str, BaseLLMClient] = {}

def get_llm_client(client_type: str = "reporting") -> BaseLLMClient:
    """
    Factory function to get an LLM client instance based on settings.
    client_type should be 'reporting' or 'reranking'.
    """
    global _clients

    config_prefix = client_type.upper()
    cache_key = client_type

    if cache_key in _clients:
        logger.debug(f"Returning cached LLM client for type: {client_type}")
        return _clients[cache_key]

    logger.info(f"Creating new LLM client instance for type: {client_type}")
    model_name = getattr(settings, f"{config_prefix}_LLM_MODEL_NAME", None)
    api_key = getattr(settings, "GEMINI_API_KEY", None)

    if not model_name:
        logger.error(f"LLM model name not configured for type: {client_type} ({config_prefix}_LLM_MODEL_NAME)")
        raise ValueError(f"LLM model name not configured for type: {client_type}")

    logger.debug(f"Config - Type: {client_type}, Model: {model_name}, API Key Set: {'Yes' if api_key else 'No (using env var?)'}")

    client_instance: BaseLLMClient

    try:
        # --- Logic to choose the right client ---
        if model_name.startswith("gemini-"):
            logger.info(f"Initializing GeminiClient for {client_type} with model {model_name}")
            client_instance = GeminiClient(api_key=api_key, model_name=model_name)
        # elif model_name.startswith("gpt-"): # Example for OpenAI
        #     # ... OpenAI client instantiation ...
        #     raise NotImplementedError("OpenAIClient not implemented yet.")
        else:
            logger.error(f"Unsupported LLM model/type configured for {client_type}: {model_name}")
            raise ValueError(f"Unsupported LLM model/type configured for {client_type}: {model_name}")

        logger.info(f"Successfully created LLM client instance for type: {client_type}")
        _clients[cache_key] = client_instance # Cache the instance
        return client_instance
    except Exception as e:
        logger.exception(f"Failed to create LLM client instance for type {client_type}")
        raise # Re-raise the exception after logging