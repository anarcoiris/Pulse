"""
knowledge/embed_client.py
=========================
Ollama embedding client for dense RAG (nomic-embed-text by default).
"""

from __future__ import annotations
import json
import urllib.request
from typing import Optional

from knowledge.pulse_config import (
    PULSE_OLLAMA_BASE_URL,
    PULSE_EMBED_MODEL,
    cfg,
)

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    _NUMPY_OK = False


class EmbedClient:
    """Embeds text via Ollama ``/api/embeddings``."""

    def __init__(
        self,
        base_url: str = PULSE_OLLAMA_BASE_URL,
        model: str = PULSE_EMBED_MODEL,
        timeout: float | None = None,
    ):
        self.base_url = base_url.rstrip("/").replace("/v1", "")
        self.model = model
        self.timeout = float(timeout if timeout is not None else cfg("llm.embed.timeout_s", 60))
        self._last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        if not _NUMPY_OK:
            self._last_error = "numpy not installed"
            return False
        try:
            health_url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception as e:
            self._last_error = str(e)
            return False

    def embed_one(self, text: str) -> Optional["np.ndarray"]:
        vecs = self.embed_batch([text])
        return vecs[0] if vecs else None

    def embed_batch(self, texts: list[str]) -> list["np.ndarray"]:
        if not _NUMPY_OK or not texts:
            return []
        url = f"{self.base_url}/api/embeddings"
        vectors = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                emb = data.get("embedding", [])
                if not emb:
                    self._last_error = "empty embedding response"
                    return []
                vec = np.array(emb, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
            except Exception as e:
                self._last_error = str(e)
                return []
        return vectors

    def status(self) -> dict:
        return {
            "available": self.available,
            "model": self.model,
            "base_url": self.base_url,
            "last_error": self._last_error,
            "numpy_ok": _NUMPY_OK,
        }


_default_embed: Optional[EmbedClient] = None


def get_embed_client() -> EmbedClient:
    global _default_embed
    if _default_embed is None:
        _default_embed = EmbedClient()
    return _default_embed
