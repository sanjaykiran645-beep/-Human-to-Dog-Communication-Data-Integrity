"""Audio upload, analysis, history, and authorized media access."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import BEHAVIOR_MODEL_VERSION, MODEL_VERSION, models
from ..config import MAX_UPLOAD_BYTES
from ..db import get_db
from ..deps import get_current_user, limit_analyze
from ..services import audit, storage
from ..services.audio import AudioError, load_processed, write_and_decode
from ..services.behavior import estimate_behavior
from ..services.explain import explain
from ..services.features import extract_features
from ..services.inference import predict_vocalization
from ..services.spectrogram import SpectrogramError, compute_spectrogram_from_file
from ..services.viz import ensure_plots, write_plots

router = APIRouter(prefix="/api", tags=["recordings"])


def _dog_or_none(db: Session, user: models.User, dog_id: str | None) -> models.Dog | None:
    if not dog_id:
        return None
    dog = db.get(models.Dog, dog_id)
    if dog is None or dog.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    return dog


def _recording_owned(db: Session, user: models.User, recording_id: str) -> models.Recording:
    rec = db.get(models.Recording, recording_id)
    if rec is None or rec.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return rec


def _serialize_recording(rec: models.Recording, analysis: models.Analysis | None = None) -> dict:
    out = {
        "id": rec.id,
        "dog_id": rec.dog_id,
        "original_filename": rec.original_filename,
        "duration_sec": rec.duration_sec,
        "sample_rate": rec.sample_rate,
        "channels": rec.channels,
        "sha256": rec.sha256,
        "file_size": rec.file_size,
        "quality_status": rec.quality_status,
        "quality": json.loads(rec.quality_json or "{}"),
        "source": rec.source,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "has_analysis": analysis is not None,
        "media_urls": {
            "processed": f"/api/recordings/{rec.id}/media/processed",
            "original": f"/api/recordings/{rec.id}/media/original",
            "waveform": f"/api/recordings/{rec.id}/media/waveform",
            "spectrogram": f"/api/recordings/{rec.id}/media/spectrogram",
            "spectrogram_data": f"/api/recordings/{rec.id}/spectrogram-data",
        },
    }
    if analysis:
        out["analysis"] = _serialize_analysis(analysis)
    return out


def _serialize_analysis(a: models.Analysis) -> dict:
    return {
        "id": a.id,
        "recording_id": a.recording_id,
        "dog_id": a.dog_id,
        "model_version": a.model_version,
        "behavior_model_version": a.behavior_model_version,
        "vocalization": a.vocalization,
        "confidence": a.confidence,
        "abstained": a.abstained,
        "probabilities": json.loads(a.probabilities_json or "{}"),
        "alternatives": json.loads(a.alternatives_json or "[]"),
        "features": json.loads(a.features_json or "{}"),
        "behavior": json.loads(a.behavior_json or "{}"),
        "explanation": json.loads(a.explanation_json or "{}"),
        "limitations": json.loads(a.limitations_json or "[]"),
        "scientific_validation_status": "unvalidated_heuristic",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def run_analysis_pipeline(
    y,
    sr: int,
    quality: dict,
    dog: models.Dog | None,
) -> dict:
    features = extract_features(y, sr)
    classification = predict_vocalization(features, quality)
    dog_dict = None
    if dog is not None:
        dog_dict = {"weight_kg": dog.weight_kg, "breed": dog.breed, "name": dog.name}
    behavior = estimate_behavior(features, classification, dog_dict)
    explanation = explain(features, quality, classification, behavior)
    return {
        "features": features,
        "classification": classification,
        "behavior": behavior,
        "explanation": explanation,
    }


@router.post("/recordings/analyze")
def analyze_recording(
    request: Request,
    request_file: UploadFile = File(..., alias="file"),
    dog_id: str | None = Form(default=None),
    source: str = Form(default="upload"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    limit_analyze(request)
    return _analyze_impl(request_file, dog_id, source, user, db)


def _analyze_impl(upload: UploadFile, dog_id: str | None, source: str, user: models.User, db: Session) -> dict:
    dog = _dog_or_none(db, user, dog_id)
    filename = upload.filename or "recording.webm"
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    rec_id = str(uuid.uuid4())
    folder = storage.recording_dir(user.id, rec_id)
    ext = storage.safe_ext(filename) or ".bin"
    original_path = folder / f"original{ext}"
    processed_path = folder / "processed.wav"
    wave_path = folder / "waveform.png"
    spec_path = folder / "spectrogram.png"

    try:
        meta = write_and_decode(data, original_path, processed_path, filename)
    except AudioError as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=400, detail=str(exc), headers={"X-Error-Code": exc.code}) from exc
    except Exception as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=400, detail="Could not process this audio file.") from exc

    y, sr = meta["y"], meta["sr"]
    quality = meta["quality"]
    try:
        write_plots(y, sr, wave_path, spec_path)
        result = run_analysis_pipeline(y, sr, quality, dog)
    except Exception as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=500, detail="Analysis failed. The recording was not saved.") from exc

    try:
        rec = models.Recording(
            id=rec_id,
            user_id=user.id,
            dog_id=dog.id if dog else None,
            original_filename=Path(filename).name[:260],
            original_path=storage.rel(original_path),
            processed_path=storage.rel(processed_path),
            spectrogram_path=storage.rel(spec_path),
            waveform_path=storage.rel(wave_path),
            content_type=upload.content_type or "application/octet-stream",
            sha256=hashlib.sha256(data).hexdigest(),
            file_size=len(data),
            duration_sec=meta["duration"],
            sample_rate=sr,
            channels=1,
            quality_status=quality.get("status", "ok"),
            quality_json=json.dumps(quality),
            source=source if source in {"upload", "microphone", "dog_response"} else "upload",
        )
        db.add(rec)
        db.flush()

        clf = result["classification"]
        analysis = models.Analysis(
            id=str(uuid.uuid4()),
            user_id=user.id,
            recording_id=rec.id,
            dog_id=rec.dog_id,
            model_version=clf.get("model_version", MODEL_VERSION),
            behavior_model_version=result["behavior"].get("model_version", BEHAVIOR_MODEL_VERSION),
            vocalization=clf["vocalization"],
            confidence=float(clf["confidence"]),
            abstained=bool(clf["abstained"]),
            probabilities_json=json.dumps(clf.get("probabilities") or {}),
            alternatives_json=json.dumps(clf.get("alternatives") or []),
            features_json=json.dumps(_jsonable(result["features"])),
            behavior_json=json.dumps(result["behavior"]),
            explanation_json=json.dumps(result["explanation"]),
            limitations_json=json.dumps(result["explanation"].get("limitations") or []),
        )
        db.add(analysis)
        db.flush()
        audit.log(db, action="recording.analyze", entity="recording", user_id=user.id, entity_id=rec.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=500, detail="Could not persist analysis record.") from exc

    return _serialize_recording(rec, analysis)


@router.get("/recordings")
def list_recordings(
    dog_id: str | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(models.Recording).where(models.Recording.user_id == user.id)
    if dog_id:
        _dog_or_none(db, user, dog_id)
        stmt = stmt.where(models.Recording.dog_id == dog_id)
    recs = list(db.scalars(stmt.order_by(models.Recording.created_at.desc()).limit(200)))
    out = []
    for rec in recs:
        analysis = db.scalar(select(models.Analysis).where(models.Analysis.recording_id == rec.id))
        out.append(_serialize_recording(rec, analysis))
    return out


@router.get("/recordings/{recording_id}")
def get_recording(
    recording_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = _recording_owned(db, user, recording_id)
    analysis = db.scalar(select(models.Analysis).where(models.Analysis.recording_id == rec.id))
    return _serialize_recording(rec, analysis)


@router.delete("/recordings/{recording_id}")
def delete_recording(
    recording_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = _recording_owned(db, user, recording_id)
    db.query(models.DogResponse).filter(
        models.DogResponse.recording_id == rec.id,
        models.DogResponse.user_id == user.id,
    ).delete()
    db.query(models.Analysis).filter(
        models.Analysis.recording_id == rec.id,
        models.Analysis.user_id == user.id,
    ).delete()
    db.delete(rec)
    audit.log(db, action="recording.delete", entity="recording", user_id=user.id, entity_id=recording_id)
    db.commit()
    storage.delete_recording_tree(user.id, recording_id)
    return {"ok": True}


def _media(user: models.User, rec: models.Recording, kind: str) -> FileResponse:
    mapping = {
        "original": rec.original_path,
        "processed": rec.processed_path,
        "spectrogram": rec.spectrogram_path,
        "waveform": rec.waveform_path,
    }
    stored = mapping.get(kind)
    if not stored:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        path = storage.resolve_owned(user.id, stored)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except FileNotFoundError:
        # If waveform or spectrogram PNG is missing but processed.wav exists, regenerate plots atomically
        if kind in {"spectrogram", "waveform"} and rec.processed_path:
            try:
                proc_path = storage.resolve_owned(user.id, rec.processed_path)
                wave_p = proc_path.parent / "waveform.png"
                spec_p = proc_path.parent / "spectrogram.png"
                ensure_plots(proc_path, wave_p, spec_p)
                path = storage.resolve_owned(user.id, stored)
            except Exception:
                raise HTTPException(status_code=404, detail="Media not found") from None
        else:
            raise HTTPException(status_code=404, detail="Media not found") from None
    media_types = {
        "original": rec.content_type or "application/octet-stream",
        "processed": "audio/wav",
        "spectrogram": "image/png",
        "waveform": "image/png",
    }
    return FileResponse(path, media_type=media_types[kind], filename=path.name)


@router.get("/recordings/{recording_id}/media/{kind}")
def get_media(
    recording_id: str,
    kind: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if kind not in {"original", "processed", "spectrogram", "waveform"}:
        raise HTTPException(status_code=404, detail="Unknown media kind")
    rec = _recording_owned(db, user, recording_id)
    return _media(user, rec, kind)


@router.get("/recordings/{recording_id}/spectrogram-data")
def get_recording_spectrogram_data(
    recording_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = _recording_owned(db, user, recording_id)
    if not rec.processed_path:
        raise HTTPException(status_code=404, detail="Processed audio not found")
    try:
        proc_path = storage.resolve_owned(user.id, rec.processed_path)
        return compute_spectrogram_from_file(proc_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Processed audio not found") from None
    except SpectrogramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (float, int, str, bool)) or obj is None:
        return obj
    try:
        return float(obj)
    except Exception:
        return str(obj)
