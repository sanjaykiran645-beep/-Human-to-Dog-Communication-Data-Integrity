# ==============================================================================
# CanineSense AI — Production Multi-Stage Container Image
# Architecture Target: linux/amd64
# Single Unified Service: Serves React SPA & FastAPI Backend on Render
# ==============================================================================

# --- Stage 1: Build Frontend SPA ---
FROM --platform=linux/amd64 node:20-alpine AS frontend-builder
WORKDIR /build/frontend

# Copy dependencies first for layer caching
COPY frontend/package.json ./
RUN npm install --prefer-offline --no-audit

# Copy source and build production bundle
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Python & Audio DSP Runtime ---
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CANINESENSE_ENV=production \
    CANINESENSE_DATA_DIR=/app/data \
    PORT=8000

# Install required system packages: FFmpeg, libsndfile1, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --upgrade pip && \
    pip install -r /app/backend/requirements.txt

# Copy backend application source
COPY backend /app/backend

# Copy built frontend assets from stage 1
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Copy bundled reference library (134 approved canine vocalizations + manifest)
COPY data/reference_library /app/data/reference_library
COPY data/models /app/data/models
COPY data/releases /app/data/releases

# Prepare data storage directories
RUN mkdir -p /app/data/storage /app/data/scratch

EXPOSE 8000

# Health check matching Render's standard health-check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/health || exit 1

# Initialize SQLite schema cleanly before spawning Uvicorn workers
CMD ["sh", "-c", "python -c 'import sys; sys.path.insert(0, \"backend\"); from app.db import init_db; init_db()' && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

