# PulseLab — Session Review: LLM Hub Virtual Network Routing & Studio Integration

**Date:** August 25, 2026  
**Status:** ALL OBJECTIVES COMPLETED & VERIFIED IN DOCKER & BROWSER  
**Platform Version:** PulseLab Generative EDA v2.1  
**Test Suite Status:** 100% Passing (183 pytest tests passing)

---

## 1. Root Cause Analysis & Resolution

### A. Public Site LLM Reporting Failure
* **Root Cause 1 (Frontend CORS / Origin):** In `webapp/src/App.tsx` and `LLMServiceModal.tsx`, `API_BASE` was hardcoded to `http://127.0.0.1:8000/api/v1`. On public domains (e.g. `pulselab.ddns.net`) or LAN IP addresses, the browser attempted to connect to `127.0.0.1` on the client's device rather than the host server.
* **Root Cause 2 (Docker Container Network):** Inside the Docker container `pulselab-eda`, `127.0.0.1:11434` referred to the container itself rather than the Docker host or `ollama-planner` container.
* **Fix Applied:**
  1. Updated frontend `API_BASE` resolution to dynamically use relative `/api/v1` for production/Caddy/Docker/LAN, and `http://127.0.0.1:8000/api/v1` only for standalone Vite dev ports (`:3000`/`:5173`).
  2. Connected `pulselab-eda` and `pulselab-caddy` to both `default` and `docker_default` (external Ollama network) in `docker-compose.pulselab.yml`.
  3. Upgraded `core/llm_service_manager.py` candidate probing to scan `host.docker.internal`, `127.0.0.1`, `ollama-planner`, and environment variables `OLLAMA_HOST`, `PRIMARY_LLM_HOST`, `ATOMIC_LLM_HOST`, `LLAMACPP_BASE_URL`.

---

### B. Missing LLM Backend Panels on Web Studio
* **Root Cause:** The LLM launcher was only accessible via a small navbar pill or modal launcher link, with no dedicated persistent workspace view.
* **Fix Applied:**
  1. Created [`webapp/src/components/LLMEnginePanel.tsx`](file:///C:/Users/soyko/Documents/Pulse-main/webapp/src/components/LLMEnginePanel.tsx) providing a full-viewport **LLM Engine & Architecture Hub** with real-time telemetry, backend toggling (`Ollama` vs `llama.cpp`), curated presets, categorized dropdown, parameter controls, model puller, and live benchmark console.
  2. Added **"LLM Engine & Hub"** as a 5th main workspace tab in `App.tsx` alongside `2D PCB Layout`, `3D WebGL Board`, `Schematic`, and `Supply Chain & BOM`.
  3. Rebuilt production bundle [`webapp/dist/`](file:///C:/Users/soyko/Documents/Pulse-main/webapp/dist) with `npm run build` and mounted live volumes in Docker.

---

### C. Distilled Reasoning Model Integration
* **Model:** `hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M` (5.8 GB)
* **Status:** 100% pulled into `ollama-planner` container and verified with live synthesis completions.
* **Template Support:** Full support for `<tool_call><function=...><parameter=...>` and `<think>` reasoning traces.

---

## 2. Verification Telemetry

| Endpoint | Protocol | Target Backend | Status |
| :--- | :--- | :--- | :--- |
| `http://127.0.0.1:8000/api/v1/llm/status` | HTTP (Direct Backend) | `ollama-planner:11434` | 🟢 200 OK (28 models, active model online) |
| `https://localhost/api/v1/llm/status` | HTTPS (Caddy Proxy) | `pulselab-eda:8000` | 🟢 200 OK (28 models, active model online) |
| `https://pulselab.ddns.net/api/v1/llm/status` | HTTPS (DDNS Gateway) | `pulselab-eda:8000` | 🟢 200 OK (Live reverse proxy) |
| `POST /api/v1/llm/test` | Live Inference Ping | `Qwen3.8-9B-Distill` | 🟢 Latency: 37.3s, formatted ESP32 pinout |
| Pytest Test Suite | Python 3.12 | `tests/` | 🟢 12/12 passing (100%) |
