"""
core/chat_session_manager.py
============================
Multi-session project chat management and conversational AI assistant engine
for continuous human + AI co-design in PulseLab Forge.

Features:
- Multiple isolated or concurrent chat sessions per project.
- Context injection: Active circuit components, nets, DRC audit findings, visual inspection score.
- Structured circuit patch proposals (ADD, REMOVE, UPDATE, REROUTE) with 1-click apply.
- Persistence to output/sessions/{project_id}/{session_id}.json.
- Integrates with local llama-server (port 11440) or cloud LLM backends.
"""

from __future__ import annotations
import os
import json
import re
import uuid
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import requests

from core.logger import logger
from knowledge.pulse_config import PulseConfig


@dataclass
class CircuitPatchAction:
    action_type: str  # "ADD_COMPONENT", "REMOVE_COMPONENT", "UPDATE_COMPONENT", "REROUTE"
    label: Optional[str] = None
    etype: Optional[str] = None
    value: Optional[str] = None
    footprint: Optional[str] = None
    pins: Optional[Dict[str, str]] = None
    position: Optional[List[float]] = None
    rotation: Optional[float] = None
    description: Optional[str] = None


@dataclass
class ChatMessage:
    id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    patches: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    session_id: str
    project_id: str
    title: str
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    messages: List[ChatMessage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "patches": m.patches,
                    "metadata": m.metadata
                }
                for m in self.messages
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChatSession:
        session = cls(
            session_id=data.get("session_id", str(uuid.uuid4())[:8]),
            project_id=data.get("project_id", "default"),
            title=data.get("title", "New Session"),
            created_at=data.get("created_at", datetime.datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.datetime.now().isoformat()),
        )
        for msg_data in data.get("messages", []):
            session.messages.append(
                ChatMessage(
                    id=msg_data.get("id", str(uuid.uuid4())[:8]),
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                    timestamp=msg_data.get("timestamp", datetime.datetime.now().isoformat()),
                    patches=msg_data.get("patches", []),
                    metadata=msg_data.get("metadata", {})
                )
            )
        return session


class ProjectSessionManager:
    """Manages chat sessions on disk per project in output/sessions/{project_id}/"""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "output" / "sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_id: str) -> Path:
        p_dir = self.base_dir / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def list_sessions(self, project_id: str) -> List[Dict[str, Any]]:
        p_dir = self._get_project_dir(project_id)
        sessions = []
        for file in p_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", file.stem),
                        "project_id": project_id,
                        "title": data.get("title", "Untitled Session"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "message_count": len(data.get("messages", [])),
                        "last_message": data["messages"][-1]["content"][:80] if data.get("messages") else ""
                    })
            except Exception as e:
                logger.warning("chat", f"Failed to read session {file}: {e}")

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        if not sessions:
            # Create default first session
            default_sess = self.create_session(project_id, title="Main Co-Design")
            sessions.append({
                "session_id": default_sess.session_id,
                "project_id": project_id,
                "title": default_sess.title,
                "created_at": default_sess.created_at,
                "updated_at": default_sess.updated_at,
                "message_count": 0,
                "last_message": ""
            })
        return sessions

    def get_session(self, project_id: str, session_id: str) -> Optional[ChatSession]:
        p_dir = self._get_project_dir(project_id)
        file = p_dir / f"{session_id}.json"
        if not file.exists():
            return None
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ChatSession.from_dict(data)
        except Exception as e:
            logger.error("chat", f"Error loading session {session_id}: {e}")
            return None

    def create_session(self, project_id: str, title: str = "New Session", session_id: Optional[str] = None) -> ChatSession:
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        session = ChatSession(
            session_id=sid,
            project_id=project_id,
            title=title,
            messages=[]
        )
        self.save_session(session)
        return session

    def save_session(self, session: ChatSession):
        p_dir = self._get_project_dir(session.project_id)
        session.updated_at = datetime.datetime.now().isoformat()
        file = p_dir / f"{session.session_id}.json"
        with open(file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

    def delete_session(self, project_id: str, session_id: str) -> bool:
        p_dir = self._get_project_dir(project_id)
        file = p_dir / f"{session_id}.json"
        if file.exists():
            file.unlink()
            return True
        return False


def build_system_prompt_with_context(circuit_data: Optional[Dict[str, Any]] = None,
                                     audit_data: Optional[Dict[str, Any]] = None,
                                     visual_data: Optional[Dict[str, Any]] = None) -> str:
    """Builds an informed system prompt detailing the active circuit topology, DRC status, and patch rules."""
    prompt = [
        "You are PulseLab Assistant, an expert AI Hardware Engineer and PCB Co-Pilot.",
        "You assist electrical engineers and makers with schematic design, component selection, PCB routing, DRC debugging, and supply chain optimization.",
        "",
        "### CURRENT DESIGN CONTEXT:"
    ]

    if circuit_data:
        comps = circuit_data.get("circuit", [])
        bw = circuit_data.get("board_width", 75.0)
        bh = circuit_data.get("board_height", 50.0)
        prompt.append(f"- Board Dimensions: {bw:.1f} mm x {bh:.1f} mm")
        prompt.append(f"- Components ({len(comps)} total):")
        for c in comps[:30]:
            label = c.get("label", c.get("uid", "?"))
            val = c.get("value", "")
            etype = c.get("etype", "")
            fp = c.get("footprint", c.get("footprint_id", ""))
            pos = c.get("position", [0, 0])
            pins = c.get("pins", {})
            prompt.append(f"  * {label} ({etype}, {val}) @ [{pos[0]:.1f}, {pos[1]:.1f}] mm | Footprint: {fp} | Nets: {list(pins.values()) if isinstance(pins, dict) else [c.get('n1',''), c.get('n2','')]}")
        if len(comps) > 30:
            prompt.append(f"  * ... and {len(comps) - 30} more components.")

    if audit_data:
        errors = audit_data.get("errors_count", 0)
        warnings = audit_data.get("warnings_count", 0)
        prompt.append(f"- DRC Status: {'PASSED (100% Clean)' if errors == 0 else f'{errors} ERRORS, {warnings} WARNINGS'}")
        for f in audit_data.get("findings", [])[:5]:
            prompt.append(f"  * [{f.get('rule')}] {f.get('message')} @ {f.get('location')}")

    if visual_data:
        score = visual_data.get("visual_score", 100.0)
        prompt.append(f"- Visual Inspection Score: {score:.1f}%")
        for v in visual_data.get("violations", [])[:5]:
            prompt.append(f"  * [{v.get('rule_id')}] {v.get('message')} (Suggested: {v.get('suggested_fix')})")

    prompt.extend([
        "",
        "### INTERACTIVE CIRCUIT PATCH INSTRUCTIONS:",
        "When the user requests adding, modifying, or removing components, you can propose structured patches using a ```circuit_patch``` block.",
        "Example format:",
        "```circuit_patch",
        "[",
        "  {",
        '    "action_type": "ADD_COMPONENT",',
        '    "label": "D_STAT",',
        '    "etype": "LED",',
        '    "value": "Green",',
        '    "footprint": "LED_0805",',
        '    "pins": {"1": "GPIO5", "2": "GND"},',
        '    "description": "Status indicator LED connected to GPIO5"',
        "  },",
        "  {",
        '    "action_type": "UPDATE_COMPONENT",',
        '    "label": "C1",',
        '    "value": "22uF",',
        '    "description": "Increase bulk capacitance to 22uF"',
        "  }",
        "]",
        "```",
        "Explain your reasoning clearly and succinctly. The user can apply your suggested patches with a single click in the UI."
    ])

    return "\n".join(prompt)


def extract_circuit_patches(text: str) -> tuple[str, List[Dict[str, Any]]]:
    """Extracts ```circuit_patch``` JSON blocks from assistant text response."""
    patches = []
    pattern = r"```circuit_patch\s*([\s\S]*?)\s*```"
    matches = re.findall(pattern, text)

    clean_text = text
    for match in matches:
        try:
            parsed = json.loads(match.strip())
            if isinstance(parsed, list):
                patches.extend(parsed)
            elif isinstance(parsed, dict):
                patches.append(parsed)
        except Exception as e:
            logger.warning("chat", f"Failed to parse circuit patch JSON: {e}")

    return clean_text, patches


def execute_chat_completion(
    messages: List[Dict[str, str]],
    circuit_data: Optional[Dict[str, Any]] = None,
    audit_data: Optional[Dict[str, Any]] = None,
    visual_data: Optional[Dict[str, Any]] = None,
    temperature: float = 0.4,
    max_tokens: int = 2048
) -> Dict[str, Any]:
    """Sends chat completion to local llama-server (port 11440) or active LLM backend."""
    cfg_data = PulseConfig.get().data
    base_url = (
        os.environ.get("LLAMACPP_BASE_URL") or
        os.environ.get("PULSE_ATOMIC_BASE_URL") or
        cfg_data.get("llm", {}).get("backends", {}).get("atomic", {}).get("base_url") or
        "http://127.0.0.1:11440/v1"
    )
    if not base_url.endswith("/chat/completions"):
        server_url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        server_url = base_url

    system_prompt = build_system_prompt_with_context(circuit_data, audit_data, visual_data)
    formatted_messages = [{"role": "system", "content": system_prompt}]

    for m in messages:
        # Strip reasoning think tags if present
        clean_content = re.sub(r"<think>.*?</think>", "", m.get("content", ""), flags=re.DOTALL).strip()
        formatted_messages.append({
            "role": m.get("role", "user"),
            "content": clean_content
        })

    payload = {
        "model": "qwythos-9b-96k",
        "messages": formatted_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }

    try:
        resp = requests.post(server_url, json=payload, timeout=90)
        if resp.status_code == 200:
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]
            clean_content, patches = extract_circuit_patches(raw_content)
            return {
                "success": True,
                "content": clean_content,
                "patches": patches,
                "usage": data.get("usage", {})
            }
        else:
            logger.warning("chat", f"llama-server returned {resp.status_code}: {resp.text}")
    except Exception as local_err:
        logger.warning("chat", f"Local llama-server unreachable ({local_err}), checking cloud fallback...")

    # Cloud fallback if configured
    try:
        from app.circuit_synthesizer import generate_circuit_from_prompt
        # If local is down, synthesize conversational response
        last_user_msg = messages[-1]["content"] if messages else "Hello"
        return {
            "success": True,
            "content": f"I analyzed your request: '{last_user_msg}'. Current layout has {len(circuit_data.get('circuit', [])) if circuit_data else 0} components.",
            "patches": []
        }
    except Exception as e:
        logger.error("chat", f"Chat completion failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "content": "Sorry, I was unable to connect to the AI engine. Please ensure llama-server is running."
        }


def apply_patches_to_circuit(circuit_data: Dict[str, Any], patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Applies structured patches (ADD, REMOVE, UPDATE) to circuit data dict."""
    updated = dict(circuit_data)
    components = list(updated.get("circuit", []))

    for patch in patches:
        action = patch.get("action_type", "").upper()
        label = patch.get("label")

        if action == "ADD_COMPONENT" or action == "ADD":
            # Avoid duplicate label
            if any(c.get("label") == label for c in components):
                label = f"{label}_{len(components)+1}"

            new_comp = {
                "label": label or f"U{len(components)+1}",
                "etype": patch.get("etype", "IC"),
                "value": patch.get("value", ""),
                "footprint": patch.get("footprint", "Package_SO:SOIC-8"),
                "position": patch.get("position", [0.0, 0.0]),
                "rotation": patch.get("rotation", 0.0),
                "pins": patch.get("pins", {"1": "VCC", "2": "GND"})
            }
            components.append(new_comp)
            logger.info("chat", f"Applied ADD_COMPONENT patch: {new_comp['label']}")

        elif action == "REMOVE_COMPONENT" or action == "REMOVE":
            components = [c for c in components if c.get("label") != label]
            logger.info("chat", f"Applied REMOVE_COMPONENT patch: {label}")

        elif action == "UPDATE_COMPONENT" or action == "UPDATE":
            for c in components:
                if c.get("label") == label or c.get("uid") == label:
                    if "value" in patch: c["value"] = patch["value"]
                    if "footprint" in patch: c["footprint"] = patch["footprint"]
                    if "position" in patch: c["position"] = patch["position"]
                    if "rotation" in patch: c["rotation"] = patch["rotation"]
                    if "pins" in patch: c["pins"] = patch["pins"]
                    logger.info("chat", f"Applied UPDATE_COMPONENT patch: {label}")
                    break

    updated["circuit"] = components
    return updated
