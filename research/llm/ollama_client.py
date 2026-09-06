"""Ollama API client for local LLM inference."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from research.config import OllamaConfig

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama's OpenAI-compatible API."""

    def __init__(self, config: OllamaConfig) -> None:
        self.config = config
        self.base_url = config.url.rstrip("/")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=self.config.timeout)
        return self._client

    def is_available(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            r = self.client.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def list_models(self) -> list[str]:
        """Return list of locally available model names."""
        try:
            r = self.client.get(f"{self.base_url}/api/tags", timeout=10)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning("Failed to list Ollama models: %s", e)
            return []

    def chat(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request to Ollama.

        Uses the /api/chat endpoint for maximum compatibility.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
                "num_ctx": 8192,
            },
        }

        try:
            r = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            data = r.json()
            return data["message"]["content"]
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def chat_stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ):
        """Stream chat completion responses."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
            },
        }

        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            yield data["message"].get("content", "")
                        if data.get("done"):
                            break
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
