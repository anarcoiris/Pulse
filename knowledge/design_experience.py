"""
knowledge/design_experience.py
==============================
Persist design outcomes and ingest lessons into the RAG knowledge base.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_EXPERIENCES_DIR = Path(__file__).resolve().parent / "experiences"


@dataclass
class DesignExperience:
    board_id: str
    timestamp: str
    mcu: str = ""
    mcu_package: str = ""
    board_size_mm: tuple = (0, 0)
    component_count: int = 0
    layer_count: int = 2
    drc_violations: int = 0
    routing_success_rate: float = 1.0
    manufacturing_target: str = "generic"
    lessons_learned: list[str] = field(default_factory=list)
    component_placement_rules: list[str] = field(default_factory=list)
    critical_nets: list[str] = field(default_factory=list)
    gerber_path: str = ""
    passed: bool = True

    def save(self, knowledge_dir: Optional[Path] = None) -> Path:
        base = Path(knowledge_dir) if knowledge_dir else _EXPERIENCES_DIR
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{self.board_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def from_file(cls, path: str | Path) -> "DesignExperience":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)

    def ingest_to_rag(self) -> int:
        """Add lessons to the electronics KB for future retrieval."""
        from knowledge.rag_engine import ElectronicsKnowledgeBase

        kb = ElectronicsKnowledgeBase()
        n = 0
        for lesson in self.lessons_learned:
            kb.ingest_text(
                f"Design experience {self.board_id} MCU {self.mcu}: {lesson}",
                source=f"Experience:{self.board_id}",
                chunk_type="design_experience",
            )
            n += 1
        for rule in self.component_placement_rules:
            kb.ingest_text(
                f"Placement rule {self.board_id}: {rule}",
                source=f"Experience:{self.board_id}#placement",
                chunk_type="design_experience",
            )
            n += 1
        return n


def record_design_outcome(
    board_id: str,
    mcu: str = "",
    lessons: Optional[list[str]] = None,
    drc_violations: int = 0,
    gerber_path: str = "",
    passed: bool = True,
    **kwargs,
) -> DesignExperience:
    """Create, save, and ingest a design experience record."""
    exp = DesignExperience(
        board_id=board_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        mcu=mcu,
        drc_violations=drc_violations,
        gerber_path=gerber_path,
        passed=passed,
        lessons_learned=lessons or [],
        **kwargs,
    )
    exp.save()
    exp.ingest_to_rag()
    return exp
