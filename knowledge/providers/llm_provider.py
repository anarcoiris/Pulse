"""Provider profiles and concrete cloud/local LLM providers for Pulse-main.

Includes support for:
- Local llama.cpp / Qwythos / Atomic
- Local Ollama
- GitHub Models Free Tier (https://models.github.ai/inference)
- OpenRouter Free Tier (https://openrouter.ai/api/v1)
- Groq Cloud Free Tier (https://api.groq.com/openai/v1)
- Google Gemini AI Studio Free Tier (https://generativelanguage.googleapis.com/v1beta/openai/)
"""

from __future__ import annotations

import os
import time
from typing import Any, Generator, Protocol, runtime_checkable
import httpx


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM model providers."""

    name: str
    provider_type: str
    model: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> str: ...

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[tuple[str, str], None, None]: ...

    def check_health(self) -> dict[str, Any]: ...


class BaseLLMProvider:
    """Base provider implementing HTTP request execution and response parsing."""

    def __init__(
        self,
        name: str,
        provider_type: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ):
        self.name = name
        self.provider_type = provider_type
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    def check_health(self) -> dict[str, Any]:
        """Perform health check on the provider endpoint."""
        start = time.perf_counter()
        try:
            resp = self._client.get("/models", timeout=5.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            healthy = resp.status_code in (200, 401, 403)
            return {
                "name": self.name,
                "provider_type": self.provider_type,
                "model": self.model,
                "healthy": healthy,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            return {
                "name": self.name,
                "provider_type": self.provider_type,
                "model": self.model,
                "healthy": False,
                "error": str(e),
                "latency_ms": latency_ms,
            }

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        stream: bool = False,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools
        return payload

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        payload = self._build_payload(
            messages, stream=False, max_tokens=max_tokens, temperature=temperature, tools=tools
        )
        resp = self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        reasoning = choice.get("reasoning_content") or ""
        if reasoning and "<think>" not in content:
            content = f"<think>\n{reasoning}\n</think>\n\n{content}"
        return content

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[tuple[str, str], None, None]:
        payload = self._build_payload(
            messages, stream=True, max_tokens=max_tokens, temperature=temperature, tools=tools
        )
        with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = httpx.json.loads(data_str)
                    delta = chunk["choices"][0]["delta"]
                    reasoning = delta.get("reasoning_content") or ""
                    if reasoning:
                        yield ("reasoning", reasoning)
                    content = delta.get("content") or ""
                    if content:
                        yield ("content", content)
                except Exception:
                    continue


class LlamaCppProvider(BaseLLMProvider):
    """Local llamacpp provider instance."""

    def __init__(self, name: str = "llamacpp", base_url: str = "http://localhost:11440", model: str = "qwythos-9b-96k", timeout: float = 120.0):
        super().__init__(
            name=name,
            provider_type="llamacpp",
            base_url=f"{base_url}/v1" if not base_url.endswith("/v1") else base_url,
            model=model,
            timeout=timeout,
        )


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider instance."""

    def __init__(self, name: str = "ollama", base_url: str = "http://localhost:11434", model: str = "llama3.2", timeout: float = 60.0):
        super().__init__(
            name=name,
            provider_type="ollama",
            base_url=f"{base_url}/v1" if not base_url.endswith("/v1") else base_url,
            model=model,
            timeout=timeout,
        )


class GitHubModelsProvider(BaseLLMProvider):
    """GitHub Models Gateway (https://models.github.ai/inference) - Free Tier available with GitHub token."""

    def __init__(
        self,
        name: str = "github_models",
        base_url: str = "https://models.github.ai/inference",
        model: str = "openai/gpt-4o",
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        key = api_key or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        super().__init__(
            name=name,
            provider_type="github",
            base_url=f"{base_url}" if base_url.endswith("/v1") or "inference" in base_url else f"{base_url}/v1",
            model=model,
            api_key=key,
            timeout=timeout,
        )


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Gateway (https://openrouter.ai/api/v1) - Free Tier models (meta-llama/llama-3.3-70b-instruct:free, etc.)."""

    def __init__(
        self,
        name: str = "openrouter",
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        super().__init__(
            name=name,
            provider_type="openrouter",
            base_url=base_url,
            model=model,
            api_key=key,
            timeout=timeout,
            extra_headers={"HTTP-Referer": "https://github.com/pulse-main", "X-Title": "Pulse Main"},
        )


class GroqProvider(BaseLLMProvider):
    """Groq Cloud (https://api.groq.com/openai/v1) - Generous Free Tier for open-weight models."""

    def __init__(
        self,
        name: str = "groq",
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        key = api_key or os.getenv("GROQ_API_KEY")
        super().__init__(
            name=name,
            provider_type="groq",
            base_url=base_url,
            model=model,
            api_key=key,
            timeout=timeout,
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini AI Studio Free Tier (https://generativelanguage.googleapis.com/v1beta/openai/)."""

    def __init__(
        self,
        name: str = "gemini",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai",
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        super().__init__(
            name=name,
            provider_type="gemini",
            base_url=base_url,
            model=model,
            api_key=key,
            timeout=timeout,
        )


def create_provider_from_config(name: str, cfg: dict[str, Any]) -> BaseLLMProvider:
    """Factory creating an LLMProvider instance from configuration dictionary."""
    ptype = cfg.get("provider", cfg.get("type", "llamacpp")).lower()
    base_url = cfg.get("base_url", "http://localhost:11440")
    model = cfg.get("model", "default")
    api_key_env = cfg.get("api_key_env")
    api_key = cfg.get("api_key")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)
    timeout = float(cfg.get("timeout", 60.0))

    if ptype in ("github", "github_models"):
        return GitHubModelsProvider(name=name, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    elif ptype == "openrouter":
        return OpenRouterProvider(name=name, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    elif ptype == "groq":
        return GroqProvider(name=name, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    elif ptype == "gemini":
        return GeminiProvider(name=name, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    elif ptype == "ollama":
        return OllamaProvider(name=name, base_url=base_url, model=model, timeout=timeout)
    else:
        return LlamaCppProvider(name=name, base_url=base_url, model=model, timeout=timeout)
