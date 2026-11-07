"""CanineSense AI HTTP application."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import SYNTH_MODEL_VERSION, BEHAVIOR_MODEL_VERSION, MODEL_VERSION, __version__
from .db import init_db
from .routers import analytics, auth, communicate, dogs, recordings
from .services.audio import decoder_status, find_ffmpeg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("caninesense")

app = FastAPI(
    title="CanineSense AI",
    version=__version__,
    description="Dog vocalization analysis and experimental human–dog communication.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

_DEFAULT_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173"
CORS_ORIGINS = [o.strip() for o in os.getenv("CANINESENSE_CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
# Extra origins allowed to embed the UI in an iframe (space separated). Default: same origin only.
FRAME_ANCESTORS = "'self' " + os.getenv("CANINESENSE_FRAME_ANCESTORS", "").strip()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = f"frame-ancestors {FRAME_ANCESTORS.strip()}"
    if request.url.path.startswith("/assets/") and response.status_code == 200:
        # Vite emits content-hashed filenames, so these are safe to cache forever.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # HTML shell and every API/media response (private user data) must never be cached.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router)
app.include_router(dogs.router)
app.include_router(recordings.router)
app.include_router(communicate.router)
app.include_router(analytics.router)


@app.get("/api/health")
def health() -> dict:
    dec = decoder_status()
    # Public endpoint: never expose host filesystem paths or tool build strings.
    dec = {k: v for k, v in dec.items() if k not in {"ffmpeg_path", "ffmpeg_version"}}
    return {
        "status": "ok" if dec["soundfile_wav"] else "degraded",
        "version": __version__,
        "vocalization_model": MODEL_VERSION,
        "behavior_model": BEHAVIOR_MODEL_VERSION,
        "synth_model": SYNTH_MODEL_VERSION,
        "accuracy_target_met": False,
        "decoder": dec,
        "notes": (
            "Vocalization labels are acoustic inferences. The 90% independent-accuracy "
            "target is not met: no dog-held-out annotated evaluation corpus is bundled."
        ),
    }


@app.on_event("startup")
def startup() -> None:
    init_db()
    exe = find_ffmpeg()
    if exe:
        log.info("FFmpeg available at %s", exe)
    else:
        log.warning(
            "FFmpeg not found. WAV/FLAC still decode. WEBM/MP3/M4A/OGG will fail until FFmpeg is installed."
        )
    log.info("CanineSense AI %s ready (model %s)", __version__, MODEL_VERSION)


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
APK_RELEASE_PATH = Path(__file__).resolve().parents[2] / "data" / "releases" / "CanineSense_AI_v1.0.0.apk"


@app.get("/api/download/apk")
@app.get("/caninesense-ai.apk")
def download_apk():
    """Serve the packaged CanineSense AI Android APK bundle."""
    if not APK_RELEASE_PATH.exists():
        raise HTTPException(status_code=404, detail="APK release package not found")
    return FileResponse(
        APK_RELEASE_PATH,
        media_type="application/vnd.android.package-archive",
        filename="CanineSense_AI_v1.0.0.apk",
    )


@app.get("/{full_path:path}")
def spa(full_path: str):
    """Serve the production frontend when `frontend/dist` exists. Never shadows `/api`."""
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")
    if not FRONTEND_DIST.exists():
        raise HTTPException(status_code=404, detail="Frontend build not present")
    root = FRONTEND_DIST.resolve()
    candidate = (FRONTEND_DIST / full_path).resolve()
    if candidate.is_relative_to(root) and candidate.is_file():
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
