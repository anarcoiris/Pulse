"""
core/llm_service_manager.py
===========================
Comprehensive LLM Service Monitor & Multi-Backend Launcher for PulseLab.
Provides dynamic configuration and switching across:
- Ollama Runtime (Docker / Native, Port :11434, :11431, :11439)
- llama-server / llamacpp (GGUF direct lane, Port :11440)
- Curated Presets: Qwen 3.8 Distill, Qwythos 9B, Gemma 4 12B, Qwen 2.5 Coder
- Fully configurable inference params (model, port, context, thinking mode, temperature)
"""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.logger import logger
from knowledge.pulse_config import cfg, PulseConfig


CANDIDATE_PORTS = [11434, 11440, 11439, 11431, 11435, 11436]

CURATED_PRESETS = [
    {
        "id": "qwen38_distill_ollama",
        "name": "Qwen 3.8 9B Distill (Ollama)",
        "model": "hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M",
        "backend": "ollama",
        "port": 11434,
        "category": "Distilled Reasoning",
        "recommended_for": "Primary Synthesis & Tool Calling",
        "description": "High-efficiency 9B distilled reasoning model with native tool calling & XML format"
    },
    {
        "id": "qwen38_9b_gguf",
        "name": "Qwen 3.8 9B Q4_K_M (llama.cpp GGUF)",
        "model": "Qwen3.8-9B-Q4_K_M.gguf",
        "backend": "llamacpp",
        "port": 11440,
        "category": "Distilled Reasoning",
        "recommended_for": "Direct CUDA / High-Speed Inference (~29 t/s)",
        "description": "Native GGUF execution on GPU 0 with Flash Attention & custom context"
    },
    {
        "id": "qwythos_9b_96k",
        "name": "Qwythos 9B Claude-Mythos 96k",
        "model": "qwythos-9b-96k:latest",
        "backend": "ollama",
        "port": 11434,
        "category": "Long Context Hardware",
        "recommended_for": "Complex Multi-Layer Schematic Synthesis",
        "description": "Specialized EDA hardware orchestrator with 96,000 token extended context"
    },
    {
        "id": "qwen3_4b_thinking",
        "name": "Qwen 3 4B Thinking (Atomic)",
        "model": "qwen3:4b-thinking-2507-q4_K_M",
        "backend": "ollama",
        "port": 11434,
        "category": "Fast Atomic",
        "recommended_for": "DRC Analysis & Fast JSON Patches",
        "description": "Ultra-fast lightweight reasoning model for real-time validation"
    },
    {
        "id": "gemma4_12b_128k",
        "name": "Gemma 4 12B IT 128k",
        "model": "gemma4-12b-128k:latest",
        "backend": "ollama",
        "port": 11434,
        "category": "Heavy Orchestration",
        "recommended_for": "Deep Architectural Analysis & Research",
        "description": "Large 12B multi-turn orchestrator with 128,000 token context"
    },
    {
        "id": "qwen25_coder_7b",
        "name": "Qwen 2.5 Coder 7B Instruct",
        "model": "qwen2.5-coder:7b-instruct",
        "backend": "ollama",
        "port": 11434,
        "category": "Code & Firmware",
        "recommended_for": "C/C++ Embedded Firmware & KiCad Python Scripts",
        "description": "Specialized code generator for embedded hardware firmware"
    },
]


def is_port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    """Quick socket probe to check if port is listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def probe_endpoint_health(base_url: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Probes an OpenAI / Ollama endpoint for health and available models."""
    clean_url = base_url.rstrip("/")
    models_url = f"{clean_url}/v1/models" if not clean_url.endswith("/v1") else f"{clean_url}/models"
    
    # 1. Try OpenAI /v1/models
    try:
        req = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                model_list = []
                for item in data.get("data") or data.get("models") or []:
                    mid = item.get("id") or item.get("name") or item.get("model")
                    if mid:
                        model_list.append(str(mid))
                endpoint_v1 = clean_url if clean_url.endswith("/v1") else f"{clean_url}/v1"
                return {
                    "online": True,
                    "endpoint": endpoint_v1,
                    "models": model_list,
                    "type": "llamacpp" if "11440" in clean_url else "ollama"
                }
    except Exception:
        pass

    # 2. Try Ollama native /api/tags
    ollama_root = clean_url.replace("/v1", "")
    try:
        req = urllib.request.Request(f"{ollama_root}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                model_list = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return {
                    "online": True,
                    "endpoint": f"{ollama_root}/v1",
                    "models": model_list,
                    "type": "ollama"
                }
    except Exception:
        pass

    return None


def list_local_gguf_models() -> List[Dict[str, Any]]:
    """Discovers .gguf models on local disk."""
    search_dirs = [
        Path(r"C:\Users\soyko\Documents\Ollama\docker\llamacpp\models"),
        Path(r"C:\Users\soyko\Documents\Ollama\models"),
        _ROOT / "knowledge" / "models"
    ]
    
    models = []
    for sdir in search_dirs:
        if sdir.exists():
            for f in sdir.glob("*.gguf"):
                size_gb = round(f.stat().st_size / (1024 ** 3), 2)
                models.append({
                    "name": f.name,
                    "path": str(f),
                    "size_gb": size_gb,
                    "source": "gguf_file"
                })
    return models


class LLMServiceManager:
    """Manages local LLM inference engines and endpoint routing with full configurability."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMServiceManager, cls).__new__(cls)
            cls._instance._user_configured_model: Optional[str] = None
            cls._user_configured_backend: Optional[str] = None
            cls._user_configured_port: Optional[int] = None
            cls._user_context_size: int = 32768
            cls._user_temperature: float = 0.6
            cls._user_thinking_mode: str = "low"
            cls._active_process = None
        return cls._instance

    def get_status(self) -> Dict[str, Any]:
        """Returns the real-time status, all models categorized, and active settings."""
        candidate_hosts = ["127.0.0.1", "host.docker.internal", "ollama-planner", "localhost"]
        
        # Incorporate environment variable hosts
        for env_k in ("OLLAMA_HOST", "PRIMARY_LLM_HOST", "ATOMIC_LLM_HOST", "LLAMACPP_BASE_URL"):
            val = os.environ.get(env_k)
            if val:
                h = val.replace("http://", "").replace("https://", "").split(":")[0].split("/")[0]
                if h and h not in candidate_hosts:
                    candidate_hosts.insert(0, h)

        # 1. Fast socket probe across candidate ports
        ports_status = {}
        for p in CANDIDATE_PORTS:
            ports_status[str(p)] = any(is_port_open(h, p, timeout=0.12) for h in candidate_hosts)

        # 2. Probe Ollama (:11434) and llama-server (:11440) specifically
        ollama_probe = None
        for h in candidate_hosts:
            if is_port_open(h, 11434, timeout=0.12):
                probe = probe_endpoint_health(f"http://{h}:11434", timeout=1.5)
                if probe and probe.get("online"):
                    ollama_probe = probe
                    ollama_probe["host"] = h
                    ollama_probe["port"] = 11434
                    break

        llamacpp_probe = None
        for h in candidate_hosts:
            if is_port_open(h, 11440, timeout=0.12):
                probe = probe_endpoint_health(f"http://{h}:11440", timeout=1.5)
                if probe and probe.get("online"):
                    llamacpp_probe = probe
                    llamacpp_probe["host"] = h
                    llamacpp_probe["port"] = 11440
                    break

        # Determine primary active probe based on user preference or availability
        active_probe = None
        preferred_backend = self._user_configured_backend or "auto"

        if preferred_backend == "llamacpp" and llamacpp_probe and llamacpp_probe.get("online"):
            active_probe = llamacpp_probe
            active_probe["port"] = 11440
        elif preferred_backend == "ollama" and ollama_probe and ollama_probe.get("online"):
            active_probe = ollama_probe
            active_probe["port"] = 11434
        else:
            # Auto fallback
            if llamacpp_probe and llamacpp_probe.get("online"):
                active_probe = llamacpp_probe
                active_probe["port"] = 11440
            elif ollama_probe and ollama_probe.get("online"):
                active_probe = ollama_probe
                active_probe["port"] = 11434
            else:
                for h in candidate_hosts:
                    for port in CANDIDATE_PORTS:
                        if is_port_open(h, port, timeout=0.12):
                            probe = probe_endpoint_health(f"http://{h}:{port}", timeout=1.5)
                            if probe and probe.get("online"):
                                active_probe = probe
                                active_probe["host"] = h
                                active_probe["port"] = port
                                break
                    if active_probe:
                        break

        # 2. Gather Ollama Models
        ollama_models = ollama_probe.get("models", []) if ollama_probe else []
        # Add default known model names if Ollama is accessible
        if not ollama_models and ports_status.get("11434"):
            ollama_models = [
                "hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M",
                "qwythos-9b-96k:latest",
                "qwen3:4b-thinking-2507-q4_K_M",
                "gemma4-12b-128k:latest",
                "qwen2.5-coder:7b-instruct"
            ]

        # 3. Gather GGUF Files
        ggufs = list_local_gguf_models()

        # 4. Build unified available models list
        all_models = []
        for g in ggufs:
            if g["name"] not in all_models:
                all_models.append(g["name"])
        for om in ollama_models:
            if om not in all_models:
                all_models.append(om)

        # 5. Resolve active model
        active_model = self._user_configured_model
        if not active_model:
            if active_probe and active_probe.get("models"):
                models = active_probe["models"]
                # Default to Qwen3.8 Distill or Qwythos if present
                preferred = [m for m in models if "qwen3.8" in m.lower() or "qwythos" in m.lower() or "gemma" in m.lower()]
                active_model = preferred[0] if preferred else models[0]
            elif ggufs:
                active_model = ggufs[0]["name"]
            else:
                active_model = "hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M"

        active_port = self._user_configured_port or (active_probe.get("port") if active_probe else (11440 if preferred_backend == "llamacpp" else 11434))
        
        if active_probe and active_probe.get("endpoint"):
            active_endpoint = active_probe["endpoint"]
        else:
            target_host = "127.0.0.1"
            for h in candidate_hosts:
                if is_port_open(h, active_port, timeout=0.12):
                    target_host = h
                    break
            active_endpoint = f"http://{target_host}:{active_port}/v1"

        return {
            "online": bool(active_probe and active_probe.get("online")),
            "service_type": active_probe.get("type", preferred_backend) if active_probe else preferred_backend,
            "active_backend": preferred_backend,
            "active_endpoint": active_endpoint,
            "active_model": active_model,
            "available_models": all_models,
            "ollama_models": ollama_models,
            "gguf_files": ggufs,
            "presets": CURATED_PRESETS,
            "port": active_port,
            "ports_status": ports_status,
            "context_size": self._user_context_size,
            "temperature": self._user_temperature,
            "thinking_mode": self._user_thinking_mode
        }

    def get_active_base_url(self) -> str:
        """Resolves the best currently available local LLM base URL."""
        status = self.get_status()
        if status.get("online"):
            return status["active_endpoint"]
        
        env_url = os.environ.get("LLAMACPP_BASE_URL") or os.environ.get("PULSE_ATOMIC_BASE_URL")
        if env_url:
            return env_url
        return "http://127.0.0.1:11434/v1"

    def configure_service(
        self,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        port: Optional[int] = None,
        context_size: Optional[int] = None,
        temperature: Optional[float] = None,
        thinking_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates user configuration in-memory and in Pulse_cfg.json."""
        if model:
            self._user_configured_model = model.strip()
        if backend:
            self._user_configured_backend = backend.strip().lower()
        if port:
            self._user_configured_port = int(port)
        if context_size:
            self._user_context_size = int(context_size)
        if temperature is not None:
            self._user_temperature = float(temperature)
        if thinking_mode:
            self._user_thinking_mode = thinking_mode.strip().lower()

        # Persist to Pulse_cfg.json
        try:
            cfg_obj = PulseConfig.get()
            if self._user_configured_model:
                cfg_obj.data.setdefault("llm", {})["model"] = self._user_configured_model
                if "backends" in cfg_obj.data["llm"]:
                    cfg_obj.data["llm"]["backends"].setdefault("primary", {})["model"] = self._user_configured_model
            if self._user_configured_port:
                port_val = self._user_configured_port
                cfg_obj.data.setdefault("llm", {})["ollama_base_url"] = f"http://localhost:{port_val}/v1"
            cfg_obj.save()
        except Exception as e:
            logger.warning("llm_service", f"Could not persist config to Pulse_cfg.json: {e}")

        return self.get_status()

    def launch_service(
        self,
        model: Optional[str] = None,
        port: Optional[int] = None,
        provider: str = "auto",
        context_size: Optional[int] = None,
        temperature: Optional[float] = None,
        thinking_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Launches, switches, or verifies the LLM service with designated model & provider.
        """
        # 1. Update config parameters
        self.configure_service(
            model=model,
            backend=provider if provider != "auto" else None,
            port=port,
            context_size=context_size,
            temperature=temperature,
            thinking_mode=thinking_mode
        )

        target_model = self._user_configured_model or model or "hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M"
        target_provider = self._user_configured_backend or provider

        # 2. If provider is llamacpp or model is a .gguf file
        if target_provider == "llamacpp" or (target_model and target_model.endswith(".gguf")):
            self._user_configured_backend = "llamacpp"
            # Launch / ensure llama-server is running
            try:
                script_path = Path(r"C:\Users\soyko\Documents\Ollama\docker\llamacpp\start-qwen38-4b.ps1")
                if script_path.exists():
                    subprocess.Popen(
                        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                    )
                    time.sleep(2.0)
            except Exception as e:
                logger.warning("llm_service", f"Failed to start llama-server script: {e}")

        else:
            # 3. Default to Ollama container / native
            self._user_configured_backend = "ollama"
            try:
                res = subprocess.run(
                    ["docker", "start", "ollama-planner"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0:
                    logger.info("llm_service", f"Started Ollama container with model '{target_model}'")
            except Exception as e:
                logger.warning("llm_service", f"Docker start ollama-planner failed: {e}")

        # Wait for service health check
        for _ in range(8):
            time.sleep(0.5)
            st = self.get_status()
            if st.get("online"):
                return {
                    "success": True,
                    "message": f"Successfully activated {st.get('service_type')} on port {st.get('port')} with model '{st.get('active_model')}'",
                    "status": st
                }

        final_st = self.get_status()
        return {
            "success": final_st.get("online", False),
            "message": f"Activated model '{target_model}' (Backend: {final_st.get('service_type')})" if final_st.get("online") else "Engine launch attempted. Verifying service...",
            "status": final_st
        }

    def stop_service(self) -> Dict[str, Any]:
        """Stops running LLM services/containers."""
        stopped = []
        try:
            res = subprocess.run(
                ["docker", "stop", "ollama-planner"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0:
                stopped.append("ollama-planner")
        except Exception:
            pass

        return {
            "success": True,
            "stopped": stopped,
            "status": self.get_status()
        }

    def pull_model(self, model_name: str) -> Dict[str, Any]:
        """Pulls a model into Ollama (e.g. from HuggingFace or Ollama library)."""
        clean_name = model_name.strip()
        if not clean_name:
            return {"success": False, "error": "Model name cannot be empty"}

        try:
            # Start background pull
            subprocess.Popen(
                ["docker", "exec", "ollama-planner", "ollama", "pull", clean_name],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
            return {
                "success": True,
                "message": f"Started pulling model '{clean_name}' in ollama-planner.",
                "model": clean_name
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_inference(
        self,
        prompt: str = "Explain what a decoupling capacitor does in 1 concise sentence.",
        model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Executes a quick benchmark completion against the active LLM backend."""
        status = self.get_status()
        if not status.get("online"):
            return {
                "success": False,
                "error": "LLM Service is offline. Please launch the service first."
            }

        primary_endpoint = status["active_endpoint"]
        target_model = model or status["active_model"]
        target_port = status.get("port") or 11434

        candidate_endpoints = []
        if primary_endpoint:
            candidate_endpoints.append(primary_endpoint.rstrip("/"))
        for h in ["127.0.0.1", "host.docker.internal", "ollama-planner", "localhost"]:
            cand = f"http://{h}:{target_port}/v1"
            if cand not in candidate_endpoints:
                candidate_endpoints.append(cand)

        temp = temperature if temperature is not None else status.get("temperature", 0.6)

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": "You are an expert hardware engineer. Provide a direct, concise response."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "max_tokens": max_tokens
        }

        last_error = None
        for endpoint in candidate_endpoints:
            url = f"{endpoint}/chat/completions"
            start_time = time.time()
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    elapsed_ms = round((time.time() - start_time) * 1000, 1)
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]["message"]
                    raw_content = choice.get("content") or ""
                    reasoning = choice.get("reasoning_content") or ""

                    # If content is inside <think> tags, separate them
                    if "<think>" in raw_content and "</think>" in raw_content:
                        parts = raw_content.split("</think>")
                        reasoning = parts[0].replace("<think>", "").strip()
                        clean_response = parts[1].strip()
                    elif raw_content:
                        clean_response = raw_content.strip()
                    else:
                        clean_response = reasoning.strip()

                    usage = data.get("usage", {})
                    completion_tokens = usage.get("completion_tokens", 0)
                    tps = round(completion_tokens / (elapsed_ms / 1000.0), 1) if elapsed_ms > 0 and completion_tokens > 0 else None

                    return {
                        "success": True,
                        "latency_ms": elapsed_ms,
                        "tokens_per_sec": tps,
                        "model_used": target_model,
                        "endpoint": endpoint,
                        "response": clean_response,
                        "reasoning": reasoning,
                        "usage": usage
                    }
            except Exception as e:
                last_error = e

        return {
            "success": False,
            "latency_ms": 0,
            "error": str(last_error) if last_error else "Failed to connect to any inference endpoint"
        }


# Global Singleton
llm_service_mgr = LLMServiceManager()
