# ==============================================================================
# CanineSense AI — Production Multi-Stage Container Image
# Architecture Target: linux/amd64
# Single Unified Service: Serves React SPA & FastAPI Backend on Render
# ==============================================================================

# --- Stage 1: Build Frontend SPA ---
FROM --platform=linux/amd64 node:20-alpine AS frontend-builder
WORKDIR /build/frontend

# Copy dependencies first for layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline --no-audit

# Copy source, lint, and build production bundle
COPY frontend/ ./
RUN npm run lint && npm run build

# --- Stage 2: Production Python & Audio DSP Runtime ---
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NUMBA_CACHE_DIR=/app/.numba_cache \
    MPLCONFIGDIR=/app/.mpl_cache \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
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

# Copy bundled reference library (134 approved canine vocalizations + manifest), evaluation samples, and promoted Engine A model
COPY data/reference_library /app/data/reference_library
COPY data/evaluation_samples /app/data/evaluation_samples
COPY data/models/candidates /app/data/models/candidates

# Prepare runtime data directories, fetch pretrained YAMNet ONNX backbone, and pre-compile Numba DSP/JIT + Matplotlib cache at build time
RUN mkdir -p /app/.numba_cache /app/.mpl_cache /app/data/storage /app/data/scratch /app/data/models/candidates /app/data/models/pretrained /app/data/releases && \
    curl -fsSL https://huggingface.co/jafet21/yamnetonnx/resolve/main/yamnet.onnx -o /app/data/models/pretrained/yamnet.onnx && \
    python -c "import sys, tempfile, pathlib, numpy as np; sys.path.insert(0, '/app/backend'); from app.services.features import extract_features; from app.services.inference import predict_vocalization, is_accuracy_target_met; from app.services.viz import write_plots; y = (0.3 * np.sin(2 * np.pi * 440.0 * np.linspace(0, 1.2, 26460))).astype(np.float32); f = extract_features(y, 22050); p = predict_vocalization(f, {'status': 'ok'}); td = pathlib.Path(tempfile.mkdtemp()); write_plots(y, 22050, td / 'w.png', td / 's.png'); print('Build warmup OK, accuracy_target_met=', is_accuracy_target_met(), 'pred=', p.get('vocalization'))"

EXPOSE 8000

# Health check matching Render's standard health-check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/health || exit 1

# Initialize SQLite schema cleanly before spawning Uvicorn workers
CMD ["sh", "-c", "python -c 'import sys; sys.path.insert(0, \"backend\"); from app.db import init_db; init_db()' && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

