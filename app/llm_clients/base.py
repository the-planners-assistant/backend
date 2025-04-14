# app/llm_clients/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional
from io import BytesIO
# If you plan to pass PIL images directly for generation:
# from PIL import Image

# Define a type hint for content parts (text, file URIs, or potentially raw image data)
LLMInputType = Union[str, List[Union[str, Dict[str, str]]]]  # Simplistic: string or list of strings/dicts

# Added definition for LLMOutputType (adjust according to your needs)
LLMOutputType = Union[str, Dict[str, Any]]

class BaseLLMClient(ABC):

    @abstractmethod
    async def generate_content(
        self,
        prompt: LLMInputType,
        stream: bool = False,
        # Add common config options (temperature, max_tokens, etc.) if desired
        **kwargs
    ) -> Union[str, Any]:  # Return type might vary for streaming
        """
        Generates content based on a prompt, potentially multimodal.
        Handles both streaming and non-streaming responses.
        """
        pass

    @abstractmethod
    async def rerank_items(
        self,
        items: List[Dict[str, Any]],
        context: str,
        # Add specific re-ranking config if needed
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Re-ranks a list of items based on context."""
        pass

    @abstractmethod
    async def upload_file(
        self,
        file_data: BytesIO,
        mime_type: str,
        display_name: Optional[str] = None
    ) -> Any:  # Return type should match the File object from the SDK
         """Uploads a file from a BytesIO object."""
         pass

    # Add other common methods as needed (e.g., embedding)