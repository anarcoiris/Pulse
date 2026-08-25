# 🚀 PulseLab Containerization, GHCR Publishing, Caddy Reverse Proxy & Service Orchestration

This guide outlines the production container architecture, GitHub Container Registry (GHCR) authentication & publishing pipeline, Caddy DDNS SSL reverse proxy configuration, and integration with the Ollama Multi-GPU Docker Orchestrator stack.

---

## 1. Architecture Overview

```
                        ┌────────────────────────────────────────────────────────┐
                        │             GitHub Actions CI/CD Workflow             │
                        │        (.github/workflows/docker-publish.yml)         │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                                                   ▼
                                ┌──────────────────────────────────────┐
                                │      GitHub Container Registry       │
                                │   ghcr.io/anarcoiris/pulse:latest   │
                                └──────────────────┬───────────────────┘
                                                   │
                ┌──────────────────────────────────┼──────────────────────────────────┐
                │                                  │                                  │
                ▼                                  ▼                                  ▼
┌──────────────────────────────┐ ┌──────────────────────────────────┐ ┌──────────────────────────────────┐
│   PulseLab Standalone Mode   │ │ Production Caddy DDNS Proxy Stack│ │  Ollama Multi-GPU Orchestration  │
│ (docker-compose.pulselab.yml)│ │  (Caddyfile + HTTPS :80/:443)    │ │(C:\Users\soyko\Documents\Ollama) │
│                              │ │                                  │ │                                  │
│ • Container: pulselab-eda    │ │ • Caddy DDNS SSL Proxy           │ │ • pulselab-eda (:8000)           │
│ • Web Studio + API (:8000)   │ │ • Reverse Proxy /api/* -> :8000  │ │ • ollama-planner (:11434, GPU 0) │
│ • Static React 19 SPA        │ │ • Static Web Studio SPA Files    │ │ • ollama-gemma   (:11431, GPU 0+1)│
│ • Embedded llamacpp engine   │ │ • Automatic Let's Encrypt SSL    │ │ • ollama-atomic  (:11439, GPU 2) │
└──────────────────────────────┘ └──────────────────────────────────┘ └──────────────────────────────────┘
```

---

## 2. GHCR Image Publishing & Authentication

To push container images manually to GitHub Container Registry (`ghcr.io`):

```bash
# 1. Login using your GitHub Personal Access Token (PAT) with write:packages scope
echo $GHCR_TOKEN | docker login ghcr.io -u anarcoiris --password-stdin

# 2. Tag and push image
docker tag ghcr.io/anarcoiris/pulse:latest ghcr.io/anarcoiris/pulse:latest
docker push ghcr.io/anarcoiris/pulse:latest
```

> **Automated Publishing**: Whenever code is pushed to `main` or a release tag (`v*`) is created, `.github/workflows/docker-publish.yml` automatically builds and pushes the image to GHCR.

---

## 3. Production Deployment with Caddy & DDNS SSL Reverse Proxy

PulseLab includes a production [`Caddyfile`](file:///c:/Users/soyko/Documents/Pulse-main/Caddyfile) configured for DDNS custom domains, security headers, compression (`zstd`/`gzip`), and automatic SSL certificates.

### A. Quick Start with Caddy
```powershell
# Launch PulseLab + Caddy Reverse Proxy for localhost
.\scripts\launch-pulselab.ps1 -Caddy

# Launch for custom DDNS domain (e.g. pulselab.ddns.net)
.\scripts\launch-pulselab.ps1 -Caddy -Domain "pulselab.ddns.net"
```

### B. Docker Compose Stack with Production Profile
```bash
SITE_ADDRESS=pulselab.ddns.net docker compose -f docker-compose.pulselab.yml --profile prod up -d
```

---

## 4. `llamacpp` Backend & Local LLM Integration

The PulseLab container image includes:
- **`llama-cpp-python` Runtime Engine**: Direct GGUF tensor execution via Python bindings inside the container.
- **REST / OpenAI Gateway Client**: Connects to `llama-server` (qwythos / Qwen3 on port 11440) or Ollama endpoints via `LLAMACPP_BASE_URL=http://host.docker.internal:11440/v1`.

---

## 5. Key Endpoints

- **Caddy Reverse Proxy / DDNS**: `https://<your-domain>/` (HTTP :80 / HTTPS :443)
- **Direct Web Studio GUI**: `http://localhost:8000/` (Modern React 19 / Three.js 2D/3D Viewer)
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
- **Health / Presets API**: `http://localhost:8000/api/v1/presets`
