# ==============================================================================
# PulseLab Generative EDA Platform - Multi-Stage Production Dockerfile
# ==============================================================================
# Stage 1: Build Modern React 19 Web Studio Frontend
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Copy webapp package manifests and install dependencies
COPY webapp/package*.json ./
RUN npm install

# Copy webapp source files and compile static production bundle
COPY webapp/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python 3.12 Generative EDA Backend & Unified Gateway
# ==============================================================================
FROM python:3.12-slim AS runtime

# System runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    build-essential \
    cmake \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000 \
    HOST=0.0.0.0

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY app/ ./app/
COPY bridge/ ./bridge/
COPY core/ ./core/
COPY knowledge/ ./knowledge/
COPY presets/ ./presets/
COPY scripts/ ./scripts/
COPY Pulse_cfg.json .

# Copy compiled frontend SPA bundle into webapp/dist for unified hosting
COPY --from=frontend-builder /build/dist ./webapp/dist

# Create output and session workspaces
RUN mkdir -p output/web_sessions logs

# Expose HTTP API and Web Studio port
EXPOSE 8000

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/presets || exit 1

# Launch FastAPI backend with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
