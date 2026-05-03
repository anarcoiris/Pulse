"""
knowledge/llm_client.py
=======================
Client unificado para interacción con LLMs vía la API de OpenAI.

Centraliza el patrón que estaba duplicado en los 3 agentes:
  - ``circuit_synthesizer.py``
  - ``firmware_synthesizer.py``
  - ``semantic_reviewer.py``

Mejoras respecto al patrón anterior:
  - Health check al endpoint ``/api/tags`` de Ollama
  - Timeout configurable (default 30s vs 600s del SDK)
  - Retry con backoff (2 intentos)
  - Método ``status()`` para mostrar en la UI
  - Mensajes de error claros cuando el servicio no está disponible
"""

from __future__ import annotations
import time
from typing import Optional


class LLMClient:
    """
    Client unificado para LLMs con health check, retry y timeout.

    Uso::

        client = LLMClient()
        if client.available:
            result = client.chat(
                system="Eres un experto en electrónica.",
                user="Diseña un divisor de tensión 5V a 3.3V.",
            )
            print(result["content"])
        else:
            print(f"LLM no disponible: {client.status()}")
    """

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen2.5:3b"
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 2

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str = "ollama",
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._api_key = api_key
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

    @property
    def available(self) -> bool:
        """Verifica rápidamente si el servicio LLM está accesible."""
        if self._client is None:
            return False
        try:
            import urllib.request
            # Ping rápido al endpoint de modelos de Ollama
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
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        """
        Envía un mensaje al LLM con retry automático.

        Returns:
            dict con keys: "content" (str), "model" (str), "tokens" (int).
            En caso de error: dict con key "error" (str).
        """
        if self._client is None:
            return {"error": self._import_error or "Cliente LLM no inicializado."}

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                choice = resp.choices[0]
                return {
                    "content": choice.message.content or "",
                    "model": self.model,
                    "tokens": getattr(resp.usage, 'total_tokens', 0) if resp.usage else 0,
                }
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.0 * (attempt + 1))  # Backoff: 1s, 2s

        return {"error": f"LLM error tras {self.MAX_RETRIES} intentos: {last_error}"}

    def status(self) -> dict:
        """Devuelve información de estado para mostrar en la UI."""
        return {
            "available": self.available,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_s": self.timeout,
            "import_error": self._import_error,
        }


# Singleton de conveniencia
_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Devuelve una instancia compartida del LLMClient."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
