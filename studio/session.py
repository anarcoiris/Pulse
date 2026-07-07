"""
studio/session.py
=================
ForgeSession — orchestrates circuit generation, review, and graph state
without pygame dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from bridge.forge_api import load_json, save_json
from core.circuit_graph import CircuitGraph
from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_backends import list_backends
from knowledge.llm_session_log import default_log_dir, new_session_id
from knowledge.llm_types import StreamChunk
from knowledge.semantic_reviewer import SemanticReviewer
from knowledge.validate_complex_apps import _pin_coverage
from studio.preview import export_schematic_preview


class ForgeSession:
    """Headless session state for Forge Studio REPL."""

    def __init__(self, backend: str = "auto"):
        self.session_id = new_session_id(prefix="studio")
        self.backend = backend
        self.graph = CircuitGraph()
        self._synth = CircuitSynthesizer(backend=backend)
        self._reviewer = SemanticReviewer(backend=backend)

    def backends_table(self) -> dict:
        return list_backends()

    def session_info(self) -> dict:
        log_dir = default_log_dir() / "sessions" / self.session_id
        return {
            "session_id": self.session_id,
            "backend": self.backend,
            "components": len(self.graph.components),
            "log_dir": str(log_dir),
        }

    def generate(
        self,
        prompt: str,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> dict:
        result = self._synth.generate_circuit_json(
            prompt,
            session_id=self.session_id,
            meta={"source": "forge_studio"},
            on_chunk=on_chunk,
        )
        if result.get("status") != "ok":
            return result

        components = result.get("components") or []
        self.graph = CircuitGraph.from_component_dicts(components)
        pin_cov = _pin_coverage(components, self._synth.pinouts_db)
        result["pin_coverage"] = pin_cov
        result["component_count"] = len(components)
        return result

    def review(self, on_chunk: Callable[[StreamChunk], None] | None = None) -> dict:
        if not self.graph.components:
            return {"error": "Sin componentes. Genera o carga un circuito primero."}
        circuit_json = json.dumps(self.graph.to_json())
        return self._reviewer.review_netlist(
            circuit_json,
            session_id=self.session_id,
            meta={"source": "forge_studio"},
            on_chunk=on_chunk,
        )

    def save(self, path: str) -> dict:
        try:
            save_json(self.graph, path)
            return {"status": "ok", "path": str(Path(path).resolve())}
        except OSError as e:
            return {"error": str(e)}

    def load(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {"error": f"Archivo no encontrado: {path}"}
        try:
            self.graph = load_json(str(p))
            return {"status": "ok", "path": str(p.resolve()), "components": len(self.graph.components)}
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            return {"error": str(e)}

    def schematic(self) -> dict:
        return export_schematic_preview(self.graph)
