"""
knowledge/llm_client.py
=======================
Client unificado para interacción con LLMs vía OpenAI-compat o Ollama native /api/chat.
All chat() calls are recorded to knowledge/data/llm_sessions/ when PULSE_LLM_LOG_IO=1.
"""

from __future__ import annotations
import time
from typing import Any, Optional

from knowledge.llm_session_log import new_call_id, record_llm_exchange
from knowledge.ollama_native import chat_native, normalize_think, ollama_native_url
from knowledge.pulse_config import (
    PULSE_OLLAMA_BASE_URL,
    PULSE_LLM_MODEL,
    PULSE_LLM_TIMEOUT,
    PULSE_LLM_MAX_TOKENS,
    PULSE_LLM_NUM_PREDICT,
    PULSE_LLM_NUM_CTX,
    PULSE_LLM_THINK,
    PULSE_LLM_API,
    PULSE_LLM_MAX_RETRIES,
    cfg,
)


class LLMClient:
    """Client unificado para LLMs con health check, retry y timeout."""

    DEFAULT_BASE_URL = PULSE_OLLAMA_BASE_URL
    DEFAULT_MODEL = PULSE_LLM_MODEL
    DEFAULT_TIMEOUT = PULSE_LLM_TIMEOUT
    DEFAULT_MAX_TOKENS = PULSE_LLM_MAX_TOKENS
    DEFAULT_NUM_PREDICT = PULSE_LLM_NUM_PREDICT
    DEFAULT_NUM_CTX = PULSE_LLM_NUM_CTX
    MAX_RETRIES = PULSE_LLM_MAX_RETRIES

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str = "ollama",
        think: str | bool | None = None,
        api_mode: str | None = None,
        backend_id: str = "primary",
        num_ctx: int | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.backend_id = backend_id
        self.num_ctx = int(num_ctx if num_ctx is not None else PULSE_LLM_NUM_CTX)
        self._api_key = api_key
        self.think = normalize_think(think if think is not None else PULSE_LLM_THINK)
        self.api_mode = (api_mode or PULSE_LLM_API).lower()
        self.native_url = ollama_native_url(base_url)
        self._client = None
        self._import_error: Optional[str] = None

        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
            )
        except ImportError:
            self._import_error = "Paquete 'openai' no instalado. Run: pip install openai"

    def _use_native(self, disable_thinking: bool) -> bool:
        if self.api_mode == "native":
            return True
        if self.api_mode == "openai":
            return False
        if disable_thinking:
            return False
        return self.think not in (False, "false")

    @property
    def available(self) -> bool:
        if self.backend_id == "atomic":
            from knowledge.atomic_lane import health_ok
            return health_ok()
        try:
            import urllib.request
            health_url = self.base_url.replace("/v1", "/api/tags")
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def chat(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        disable_thinking: bool = False,
        think: str | bool | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> dict:
        """history: optional prior turns (e.g. [{"role": "user", ...},
        {"role": "assistant", ...}]) inserted between system and the final user
        message — used for continuation turns on truncated output (see
        circuit_synthesizer._continue_truncated_json)."""
        if max_tokens is None:
            max_tokens = self.DEFAULT_NUM_PREDICT
        if temperature is None:
            temperature = float(cfg("llm.default_temperature", 0.3))

        think_level = normalize_think(think if think is not None else self.think)
        if disable_thinking:
            think_level = False

        caller = str(kwargs.pop("caller", "unknown"))
        session_id = str(kwargs.pop("session_id", new_call_id()))
        meta: dict[str, Any] = dict(kwargs.pop("meta", {}) or {})

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user})

        api = "native" if self._use_native(disable_thinking) else "openai"
        t0 = time.perf_counter()
        if api == "native":
            result = self._chat_native(
                messages=messages,
                think=think_level,
                temperature=temperature,
                num_predict=max_tokens,
                num_ctx=self.num_ctx,
            )
        else:
            result = self._chat_openai(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                disable_thinking=disable_thinking,
                num_ctx=self.num_ctx,
                **kwargs,
            )
        duration_ms = (time.perf_counter() - t0) * 1000

        call_id = new_call_id()
        attempt_no = int(meta.get("attempt", 0) or 0)
        log_path = record_llm_exchange(
            call_id=call_id,
            session_id=session_id,
            caller=caller,
            api=api,
            model=self.model,
            think=think_level,
            system=system,
            user=user,
            response=result,
            duration_ms=duration_ms,
            attempt=attempt_no,
            meta=meta,
            backend_id=self.backend_id,
            max_tokens=max_tokens,
            num_ctx=self.num_ctx,
        )
        if log_path:
            result["log_path"] = str(log_path)
            result["call_id"] = call_id
            result["session_id"] = session_id
            result["session_dir"] = str(log_path.parent)

        if "done_reason" not in result:
            raw = result.get("raw") or {}
            result["done_reason"] = raw.get("done_reason") or raw.get("finish_reason") or ""

        return result

    def _chat_native(
        self,
        messages: list[dict[str, str]],
        think: str | bool,
        temperature: float,
        num_predict: int,
        num_ctx: int,
    ) -> dict:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            result = chat_native(
                api_url=self.native_url,
                model=self.model,
                messages=messages,
                think=think,
                stream=False,
                temperature=temperature,
                num_predict=num_predict,
                num_ctx=num_ctx,
                timeout=self.timeout,
            )
            if "error" not in result:
                return result
            last_error = result["error"]
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(1.0 * (attempt + 1))
        return {"error": f"LLM native error tras {self.MAX_RETRIES} intentos: {last_error}"}

    def _chat_openai(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        disable_thinking: bool,
        num_ctx: int | None = None,
        **kwargs,
    ) -> dict:
        if self._client is None:
            return {"error": self._import_error or "Cliente LLM no inicializado."}

        call_kwargs = dict(kwargs)
        if json_mode and "response_format" not in call_kwargs:
            call_kwargs["response_format"] = {"type": "json_object"}

        from knowledge.llm_json import is_reasoning_model
        if is_reasoning_model(self.model):
            call_kwargs.pop("response_format", None)

        if disable_thinking or json_mode:
            extra = dict(call_kwargs.pop("extra_body", {}) or {})
            extra.setdefault("reasoning_effort", "none")
            if num_ctx is not None:
                extra.setdefault("num_ctx", num_ctx)
            call_kwargs["extra_body"] = extra

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **call_kwargs,
                )
                choice = resp.choices[0]
                msg = choice.message
                content = msg.content or ""
                thinking = ""
                if not content.strip():
                    for attr in ("thinking", "reasoning"):
                        alt = getattr(msg, attr, None) or ""
                        if alt.strip():
                            content = alt
                            break
                else:
                    thinking = getattr(msg, "thinking", None) or ""
                finish_reason = getattr(choice, "finish_reason", None) or ""
                return {
                    "content": content,
                    "thinking": thinking,
                    "model": self.model,
                    "tokens": getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
                    "done_reason": finish_reason,
                    "raw": {"finish_reason": finish_reason},
                }
            except Exception as e:
                last_error = e
                call_kwargs.pop("response_format", None)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.0 * (attempt + 1))

        return {"error": f"LLM error tras {self.MAX_RETRIES} intentos: {last_error}"}

    def status(self) -> dict:
        return {
            "available": self.available,
            "model": self.model,
            "base_url": self.base_url,
            "native_url": self.native_url,
            "api_mode": self.api_mode,
            "think": self.think,
            "timeout_s": self.timeout,
            "backend_id": self.backend_id,
            "num_ctx": self.num_ctx,
            "num_predict": self.DEFAULT_NUM_PREDICT,
            "import_error": self._import_error,
        }


_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
