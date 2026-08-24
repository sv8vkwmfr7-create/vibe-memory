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


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider.

    Uses the Messages API (https://docs.anthropic.com/en/api/messages).

    Args:
        api_key: Anthropic API key (or set ANTHROPIC_AUTH_TOKEN env var)
        model: Model name (default: claude-sonnet-4-20250514)
        timeout: Default timeout in seconds
        max_retries: Retry count
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        import os
        self.api_key = api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("ANTHROPIC_API_KEY", ""))
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._api_version = "2023-06-01"

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> dict:
        """
        Send chat request to Anthropic Messages API.

        Converts OpenAI-style messages to Anthropic format.
        """
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self._api_version,
        }

        # Convert OpenAI-style messages to Anthropic format
        # System message extracted separately
        system = ""
        anthropic_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system = content
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": content,
                })

        body = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system

        data = json.dumps(body).encode("utf-8")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                content = result["content"][0]["text"]

                return {
                    "content": content,
                    "model": result.get("model", self.model),
                    "usage": {
                        "prompt_tokens": result["usage"]["input_tokens"],
                        "completion_tokens": result["usage"]["output_tokens"],
                        "total_tokens": result["usage"]["input_tokens"] + result["usage"]["output_tokens"],
                    },
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


class TransformersProvider(LLMProvider):
    """
    Local Hugging Face transformers provider.

    Runs small models locally with no API key needed.
    Good models for edge classification: Qwen2.5-0.5B-Instruct, SmolLM2-1.7B-Instruct.

    Args:
        model_name: Hugging Face model name (default: Qwen/Qwen2.5-0.5B-Instruct)
        device: "cpu" or "cuda" (default: auto-detect)
        timeout: Generation timeout in seconds
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
        device: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 1,
    ):
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self._model = None
        self._tokenizer = None
        self._device = device

    @property
    def name(self) -> str:
        return f"local:{self.model_name}"

    def _load(self):
        """Lazy-load model and tokenizer."""
        if self._model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )

        if self._device:
            self._model.to(self._device)
        elif torch.cuda.is_available():
            self._model.to("cuda")
            self._device = "cuda"
        else:
            self._device = "cpu"

        self._model.eval()

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: Optional[float] = None,
    ) -> dict:
        """
        Generate response with local model.

        Converts OpenAI-style messages to chat template format.
        """
        self._load()

        import torch

        # Build prompt using chat template
        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else 0.01,
                do_sample=temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Decode only the generated part
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        content = self._tokenizer.decode(generated, skip_special_tokens=True)

        return {
            "content": content,
            "model": self.model_name,
            "usage": {
                "prompt_tokens": int(inputs["input_ids"].shape[1]),
                "completion_tokens": int(generated.shape[0]),
                "total_tokens": int(inputs["input_ids"].shape[1] + generated.shape[0]),
            },
        }


# --- Factory ---

def create_provider(
    provider: str = "openai",
    **kwargs,
) -> LLMProvider:
    """
    Create an LLM provider.

    Args:
        provider: "openai" | "anthropic" | "transformers"
        **kwargs: Passed to the specific provider constructor

    Returns:
        LLMProvider instance
    """
    if provider == "openai":
        return OpenAIProvider(**kwargs)
    if provider == "anthropic":
        return AnthropicProvider(**kwargs)
    if provider == "transformers":
        return TransformersProvider(**kwargs)
    raise ValueError(f"Unknown LLM provider: {provider}")