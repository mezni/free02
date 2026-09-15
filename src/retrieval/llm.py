"""Retrieval LLM abstraction: OpenAI-compatible client and deterministic stub."""

from abc import ABC, abstractmethod

import httpx

from src.config import settings

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question using only the provided "
    "context. If the context does not contain the answer, say so. Cite the "
    "source file for each claim."
)


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return a completion for `prompt`."""


class OpenAICompatibleLLM(LLM):
    """Chat-completions client for OpenAI and compatible endpoints."""

    def __init__(
        self,
        api_key: str = settings.llm_api_key,
        model: str = settings.llm_model,
        base_url: str = settings.llm_base_url,
        timeout: float = settings.llm_timeout,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(self, prompt: str) -> str:
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._client.close()


class StubLLM(LLM):
    """Deterministic fallback used when no LLM API key is configured."""

    def complete(self, prompt: str) -> str:
        return "[stub] No LLM configured (set LLM_API_KEY); returning retrieved context only."


__all__ = ["LLM", "SYSTEM_PROMPT", "OpenAICompatibleLLM", "StubLLM"]