import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from .openai_client import NormalizedChatOpenAI
from .base_client import BaseLLMClient
from .validators import validate_model

class OllamaClient(BaseLLMClient):
    """Native Client for Ollama using OpenAI-compatible layer.
    
    This uses ChatOpenAI to ensure full tool calling support while injecting
    native Ollama options (like num_ctx) via the extra_body parameter.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance for Ollama."""
        self.warn_if_unknown_model()
        
        env_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        resolved_url = self.base_url or env_base
        
        # Ensure we have /v1 suffix for the OpenAI-compatible endpoint
        if not resolved_url.endswith("/v1") and not resolved_url.endswith("/v1/"):
            resolved_url = resolved_url.rstrip("/") + "/v1"

        # Resolve num_ctx from environment or config
        num_ctx = self.kwargs.get("ollama_num_ctx") or int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

        llm_kwargs = {
            "model": self.model,
            "openai_api_key": "ollama", # Required by ChatOpenAI but ignored by Ollama
            "base_url": resolved_url,
            "extra_body": {
                "options": {
                    "num_ctx": num_ctx
                }
            }
        }

        # Forward standard LangChain kwargs
        _PASSTHROUGH = ("temperature", "top_p", "top_k", "callbacks")
        for key in _PASSTHROUGH:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model("ollama", self.model)
