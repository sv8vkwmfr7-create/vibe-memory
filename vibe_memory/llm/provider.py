"""
LLM Provider — abstraction layer + OpenAI-compatible implementation

Supports any OpenAI-compatible API (OpenAI / Ollama / vLLM / Groq / local models).
AnthropicProvider can be added for Claude API support.

Usage:
    from vibe_memory.llm import LLMProvider, OpenAIProvider

    provider = OpenAIProvider(
        api_key="sk-xxx",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )
    response = provider.chat(messages)
"""

from abc import ABC, abstractmethod
from typing import Optional
import json
import urllib.request
import urllib.error


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: float = 30.0,
    ) -> dict:
        """
        Send a chat request.

        Args:
            messages: [{"role": "system"/"user", "content": "..."}]
            temperature: Sampling temperature
            max_tokens: Max generation tokens
            timeout: Timeout in seconds

        Returns:
            {"content": str, "model": str, "usage": {...}}

        Raises:
            LLMError: On failure
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...


class LLMError(Exception):
    """LLM call exception."""
    pass


class OpenAIProvider(LLMProvider):
    """
    OpenAI-compatible API provider.

    Args:
        api_key: API key
        base_url: API base URL (default: OpenAI)
        model: Model name
        timeout: Default timeout in seconds
        max_retries: Retry count
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> dict:
        """
        Send chat request to OpenAI-compatible API.

        Returns:
            {"content": str, "model": str, "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}}
        """
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                choice = result["choices"][0]
                content = choice["message"]["content"]

                return {
                    "content": content,
                    "model": result.get("model", self.model),
                    "usage": result.get("usage", {}),
                }

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                last_error = LLMError(
                    f"HTTP {e.code} from {self.name}: {error_body[:500]}"
                )
                if e.code == 429 and attempt < self.max_retries:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                break

            except urllib.error.URLError as e:
                last_error = LLMError(f"Connection error to {self.name}: {e.reason}")
                if attempt < self.max_retries:
                    import time
                    time.sleep(1)
                    continue
                break

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = LLMError(f"Invalid response from {self.name}: {e}")
                break

        raise last_error or LLMError(f"Unknown error calling {self.name}")


# --- Factory ---

def create_provider(
    provider: str = "openai",
    **kwargs,
) -> LLMProvider:
    """
    Create an LLM provider.

    Args:
        provider: "openai" | "anthropic" (future)
        **kwargs: Passed to the specific provider constructor

    Returns:
        LLMProvider instance
    """
    if provider == "openai":
        return OpenAIProvider(**kwargs)
    raise ValueError(f"Unknown LLM provider: {provider}")