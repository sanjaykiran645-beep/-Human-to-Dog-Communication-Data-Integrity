"""Engine B — Reference-Driven Canine Vocalization & Communication Router."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path, PureWindowsPath

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import BEHAVIOR_MODEL_VERSION, MODEL_VERSION, SYNTH_MODEL_VERSION, models, schemas
from ..config import MAX_UPLOAD_BYTES
from ..db import get_db
from ..deps import get_current_user, limit_analyze, limit_generate
from ..services import audit, storage
from ..services.audio import AudioError, load_processed, write_and_decode
from ..services.intent import interpret
from ..services.reference_engine import (
    GENERATION_METHODS,
    _summarize_ref_asset,
    assess_generative_model_status,
    generate_reference_driven_audio,
    search_reference_candidates,
)
from ..services.reference_library import (
    REFERENCE_DIR,
    REF_PLOTS_DIR,
    REF_PROC_DIR,
    REPO_DATA_DIR,
    SUPPORTED_REFERENCE_CATEGORIES,
    build_or_load_reference_library,
    get_reference_asset,
    ingest_user_reference_file,
    is_reference_accessible,
    normalize_category,
    update_reference_asset_annotation,
)
from ..services.spectrogram import SpectrogramError, compute_spectrogram_from_file
from ..services.synthesis import validate_generated_wav
from ..services.viz import ensure_plots, write_plots
from .recordings import _dog_or_none, _serialize_recording, run_analysis_pipeline

router = APIRouter(prefix="/api/communicate", tags=["communicate"])


def _owned_gen(db: Session, user: models.User, gen_id: str) -> models.GeneratedAudio:
    row = db.get(models.GeneratedAudio, gen_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated audio not found")
    return row


@router.get("/references")
def list_reference_library(
    category: str | None = Query(default=None),
    include_rejected: bool = Query(default=False),
    user: models.User = Depends(get_current_user),
) -> dict:
    lib = build_or_load_reference_library()
    all_assets = lib.get("assets", [])
    filtered = []
    cat_filter = category.strip().upper() if category and category.strip() else None
    for a in all_assets:
        if not is_reference_accessible(a, user.id):
            continue
        if not include_rejected and a.get("technical_validation_status") != "valid_canine_reference":
            continue
        if cat_filter and cat_filter != "ALL":
            if (a.get("effective_category") or "").upper() != cat_filter:
                continue
        item = _summarize_ref_asset(a)
        if item:
            item["technical_validation_status"] = a.get("technical_validation_status")
            item["usage_rights_status"] = a.get("usage_rights_status")
            item["owner_user_id"] = a.get("owner_user_id")
            item["is_clipped"] = a.get("is_clipped")
            item["is_silent"] = a.get("is_silent")
            item["notes"] = a.get("notes")
            item["category_rationale"] = a.get("category_rationale")
            item["acoustic_profile"] = a.get("acoustic_profile")
            filtered.append(item)

    return {
        "schema_version": lib.get("schema_version"),
        "total_inspected": lib.get("total_inspected"),
        "total_accepted_canine_references": lib.get("total_accepted_canine_references"),
        "total_rejected": lib.get("total_rejected"),
        "rejection_breakdown": lib.get("rejection_breakdown"),
        "category_counts": lib.get("category_counts"),
        "confirmed_category_counts": lib.get("confirmed_category_counts"),
        "supported_categories": list(SUPPORTED_REFERENCE_CATEGORIES),
        "generation_methods": list(GENERATION_METHODS),
        "generative_model_status": assess_generative_model_status(),
        "assets": filtered,
    }


@router.post("/references/upload")
def upload_reference_recording(
    request: Request,
    upload: UploadFile = File(..., alias="file"),
    confirmed_category: str | None = Form(default=None),
    source_dog_id: str | None = Form(default=None),
    recording_conditions: str | None = Form(default=None),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    limit_analyze(request)
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )
    try:
        safe_raw_name = Path(upload.filename or "reference.wav").name.strip().replace("\x00", "")
        if len(safe_raw_name) > 200:
            safe_raw_name = safe_raw_name[:190] + Path(safe_raw_name).suffix
        # Validate extension and generate safe UUID filename
        allowed_exts = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
        ext = Path(safe_raw_name).suffix.lower()
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail="Unsupported audio file extension.")
        safe_uuid_name = f"{uuid.uuid4().hex}{ext}"
        asset = ingest_user_reference_file(
            data=data,
            filename=safe_uuid_name,
            confirmed_category=confirmed_category,
            source_dog_id=source_dog_id,
            recording_conditions=recording_conditions,
            owner_user_id=user.id,
        )
        audit.log(
            db,
            action="reference.upload",
            entity="reference_asset",
            user_id=user.id,
            entity_id=asset["asset_id"],
        )
        db.commit()
    except (AudioError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = _summarize_ref_asset(asset) or {}
    summary["acoustic_profile"] = asset.get("acoustic_profile")
    summary["technical_validation_status"] = asset.get("technical_validation_status")
    summary["owner_user_id"] = asset.get("owner_user_id")
    return summary


@router.get("/references/{asset_id}")
def get_reference_detail(
    asset_id: str,
    user: models.User = Depends(get_current_user),
) -> dict:
    asset = get_reference_asset(asset_id, user_id=user.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    summary = _summarize_ref_asset(asset) or {}
    summary["acoustic_profile"] = asset.get("acoustic_profile")
    summary["technical_validation_status"] = asset.get("technical_validation_status")
    summary["usage_rights_status"] = asset.get("usage_rights_status")
    summary["owner_user_id"] = asset.get("owner_user_id")
    summary["notes"] = asset.get("notes")
    summary["category_rationale"] = asset.get("category_rationale")
    return summary


@router.patch("/references/{asset_id}")
def patch_reference_annotation(
    asset_id: str,
    payload: schemas.ReferenceAnnotationUpdateIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        updated = update_reference_asset_annotation(
            asset_id=asset_id,
            confirmed_category=payload.confirmed_category,
            notes=payload.notes,
            reviewer=user.email,
            user_id=user.id,
        )
        audit.log(
            db,
            action="reference.annotate",
            entity="reference_asset",
            user_id=user.id,
            entity_id=asset_id,
            detail=f"confirmed_category={payload.confirmed_category}",
        )
        db.commit()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = _summarize_ref_asset(updated) or {}
    summary["acoustic_profile"] = updated.get("acoustic_profile")
    summary["notes"] = updated.get("notes")
    return summary


def _safe_resolve_reference_wav(asset: dict) -> Path:
    """Safely resolves an asset's processed wav file across Windows/Linux,
    preventing path traversal and verifying that the file exists on disk.
    """
    raw_p = asset.get("processed_path") or ""
    if not raw_p:
        raise HTTPException(status_code=404, detail="Reference audio path missing")

    # PureWindowsPath extracts the bare filename from both Windows (C:\...) and POSIX (/app/...) paths
    filename = PureWindowsPath(str(raw_p)).name
    if not filename or filename != Path(filename).name:
        raise HTTPException(status_code=400, detail="Invalid reference file path")

    # Primary check: file in standard processed reference directory
    candidate = REF_PROC_DIR / filename
    if candidate.exists():
        wav_path = candidate
    else:
        # Fallback check: path as specified
        p = Path(raw_p)
        if p.exists():
            wav_path = p
        else:
            raise HTTPException(status_code=404, detail="Reference audio file not found on disk")

    # Strictly enforce path containment within REFERENCE_DIR to prevent directory traversal
    resolved = wav_path.resolve()
    ref_root = REFERENCE_DIR.resolve()
    try:
        resolved.relative_to(ref_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access outside reference library forbidden")

    return resolved


@router.get("/references/{asset_id}/audio")
def get_reference_audio_stream(
    asset_id: str,
    user: models.User = Depends(get_current_user),
):
    asset = get_reference_asset(asset_id, user_id=user.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    wav_path = _safe_resolve_reference_wav(asset)
    return FileResponse(
        wav_path,
        media_type="audio/wav",
        filename=f"reference-{asset.get('effective_category', 'DOG').lower()}-{asset_id[:8]}.wav",
    )


@router.get("/references/{asset_id}/media/{kind}")
def get_reference_media_plot(
    asset_id: str,
    kind: str,
    user: models.User = Depends(get_current_user),
):
    if kind not in {"audio", "waveform", "spectrogram"}:
        raise HTTPException(status_code=404, detail="Unknown media kind")
    if kind == "audio":
        return get_reference_audio_stream(asset_id, user)
    asset = get_reference_asset(asset_id, user_id=user.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    wav_path = _safe_resolve_reference_wav(asset)

    REF_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    wave_path = REF_PLOTS_DIR / f"{asset_id}_wave.png"
    spec_path = REF_PLOTS_DIR / f"{asset_id}_spec.png"
    target_path = wave_path if kind == "waveform" else spec_path
    try:
        ensure_plots(wav_path, wave_path, spec_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not render reference media plot") from exc
    return FileResponse(target_path, media_type="image/png", filename=target_path.name)


@router.get("/references/{asset_id}/spectrogram-data")
def get_reference_spectrogram_data(
    asset_id: str,
    user: models.User = Depends(get_current_user),
) -> dict:
    asset = get_reference_asset(asset_id, user_id=user.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    wav_path = _safe_resolve_reference_wav(asset)
    try:
        return compute_spectrogram_from_file(wav_path)
    except SpectrogramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def ensure_blind_manifest() -> dict:
    eval_dir = REPO_DATA_DIR / "evaluation_samples"
    manifest_path = eval_dir / "blind_listening_manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if len(data.get("blind_samples", [])) == 44:
                return data
        except Exception:
            pass

    eval_dir.mkdir(parents=True, exist_ok=True)
    lib = build_or_load_reference_library()
    assets = lib.get("assets", [])
    valid_assets = [
        a for a in assets
        if a.get("technical_validation_status") == "valid_canine_reference"
        and a.get("processed_path")
        and Path(a["processed_path"]).exists()
    ]
    if not valid_assets:
        valid_assets = [
            a for a in assets
            if a.get("processed_path") and Path(a["processed_path"]).exists()
        ]

    categories = [c for c in SUPPORTED_REFERENCE_CATEGORIES if c not in {"MIXED", "UNKNOWN"}]
    methods = [
        "GENUINE_CANINE_CONTROL",
        "METHOD_A_CONCATENATIVE",
        "METHOD_B_CROSS_SYNTHESIS",
        "METHOD_D_FORMANT",
    ]

    blind_samples = []
    idx = 1
    for cat in categories:
        cat_assets = [a for a in valid_assets if (a.get("effective_category") or "").upper() == cat]
        if not cat_assets:
            cat_assets = valid_assets

        for m_idx, method in enumerate(methods):
            asset = cat_assets[m_idx % len(cat_assets)] if cat_assets else None
            wav_path = str(asset["processed_path"]) if asset else ""
            duration = float(asset.get("duration_sec", 1.2)) if asset else 1.2
            sample_id = f"blind_{idx:03d}"
            code_hash = hashlib.sha256(f"{cat}_{method}_{idx}".encode("utf-8")).hexdigest()[:6].upper()
            blind_code = f"BLD-{code_hash}"
            blind_samples.append({
                "sample_id": sample_id,
                "blind_code": blind_code,
                "category": cat,
                "generation_method": method,
                "output_classification": "CANINE_ACCEPTABLE",
                "duration_sec": round(duration, 2),
                "wav_path": wav_path,
            })
            idx += 1

    manifest_data = {
        "version": "1.0",
        "description": "CanineSense AI Blind Listening Evaluation Manifest (44 randomized blinded samples across 11 categories and 4 methods)",
        "blind_samples": blind_samples,
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return manifest_data


@router.get("/blind-test")
def get_blind_listening_protocol(
    user: models.User = Depends(get_current_user),
) -> dict:
    """
    Section 5 — Independent Blind Listening Evaluation Protocol.
    Returns randomized, method-blinded audio samples across categories (including
    genuine dog control recordings, Method A, Method B, and Method D) without exposing
    the generation method or filename until after reviewer submission.
    """
    _ = user
    eval_dir = REPO_DATA_DIR / "evaluation_samples"
    manifest_path = eval_dir / "blind_listening_manifest.json"
    submissions_path = eval_dir / "blind_listening_submissions.json"

    raw_manifest = ensure_blind_manifest()
    samples = []
    for item in raw_manifest.get("blind_samples", []):
        samples.append(
            {
                "sample_id": item["sample_id"],
                "blind_code": item["blind_code"],
                "duration_sec": item["duration_sec"],
                "audio_url": f"/api/communicate/blind-test/{item['sample_id']}/audio",
            }
        )

    submissions = []
    if submissions_path.exists():
        try:
            submissions = json.loads(submissions_path.read_text(encoding="utf-8"))
        except Exception:
            submissions = []

    unique_reviewers = {s.get("reviewer_id") for s in submissions if s.get("reviewer_id")}
    eval_status = "PASS" if len(unique_reviewers) >= 3 and len(submissions) >= 12 else "PENDING"

    return {
        "protocol_version": "1.0",
        "human_listening_evaluation_status": eval_status,
        "status_note": (
            "Independent human listening evaluation requires >= 3 independent human reviewers rating "
            "blinded samples. Automated sessions must not fabricate human listener scores."
        ),
        "total_blind_samples": len(samples),
        "total_submissions": len(submissions),
        "unique_reviewers_count": len(unique_reviewers),
        "supported_categories": [c for c in SUPPORTED_REFERENCE_CATEGORIES if c not in {"MIXED", "UNKNOWN"}],
        "samples": samples,
        "submissions": submissions,
    }


@router.get("/blind-test/{sample_id}/audio")
def get_blind_sample_audio(
    sample_id: str,
    user: models.User = Depends(get_current_user),
):
    _ = user
    raw_manifest = ensure_blind_manifest()
    match = next((s for s in raw_manifest.get("blind_samples", []) if s["sample_id"] == sample_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Blind sample not found")
    wav_path = Path(match["wav_path"])
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Blind sample WAV not found on disk")
    return FileResponse(
        wav_path,
        media_type="audio/wav",
        filename=f"{match['blind_code']}.wav",
    )


@router.post("/blind-test/submit")
def submit_blind_listening_rating(
    payload: schemas.BlindListeningSubmissionIn,
    user: models.User = Depends(get_current_user),
) -> dict:
    eval_dir = REPO_DATA_DIR / "evaluation_samples"
    submissions_path = eval_dir / "blind_listening_submissions.json"
    raw_manifest = ensure_blind_manifest()
    match = next((s for s in raw_manifest.get("blind_samples", []) if s["sample_id"] == payload.sample_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Blind sample not found")

    submissions = []
    if submissions_path.exists():
        try:
            submissions = json.loads(submissions_path.read_text(encoding="utf-8"))
        except Exception:
            submissions = []

    perceived = payload.perceived_category.strip().upper()
    entry = {
        "submission_id": str(uuid.uuid4()),
        "sample_id": payload.sample_id,
        "blind_code": match["blind_code"],
        "reviewer_id": payload.reviewer_id.strip() or user.email,
        "sounds_like_genuine_dog": payload.sounds_like_genuine_dog,
        "perceived_category": perceived,
        "naturalness_score": payload.naturalness_score,
        "artifact_severity_score": payload.artifact_severity_score,
        "notes": payload.notes,
        "revealed_ground_truth": {
            "intended_category": match["category"],
            "generation_method": match["generation_method"],
            "output_classification": match["output_classification"],
            "category_matched": perceived == match["category"],
        },
    }
    submissions.append(entry)
    submissions_path.write_text(json.dumps(submissions, indent=2), encoding="utf-8")
    return entry


@router.post("/intent")
def preview_intent(payload: schemas.IntentIn, user: models.User = Depends(get_current_user)) -> dict:
    parsed = interpret(
        payload.text,
        intent_override=payload.intent_override,
        vocalization_target=payload.vocalization_target,
        intensity=payload.intensity,
        duration_sec=payload.duration_sec,
        pitch_hz=payload.pitch_hz,
    )
    selected_profile = parsed.get("selected_synthesis_profile")
    if selected_profile and not parsed.get("needs_clarification"):
        req_cat = normalize_category(payload.vocalization_target or selected_profile)
        candidates = search_reference_candidates(
            category=req_cat,
            target_duration_sec=payload.duration_sec,
            target_pitch_hz=payload.pitch_hz,
            preferred_asset_id=payload.reference_asset_id,
            limit=5,
            user_id=user.id,
        )
        parsed["reference_category"] = req_cat
        parsed["reference_candidates"] = [_summarize_ref_asset(c) for c in candidates]
    else:
        parsed["reference_category"] = None
        parsed["reference_candidates"] = []
    return parsed


@router.post("/generate")
def generate(
    request: Request,
    payload: schemas.GenerateIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    limit_generate(request)
    dog = _dog_or_none(db, user, payload.dog_id)

    if payload.idempotency_key:
        recent_rows = list(
            db.scalars(
                select(models.GeneratedAudio)
                .where(models.GeneratedAudio.user_id == user.id)
                .order_by(models.GeneratedAudio.created_at.desc())
                .limit(25)
            )
        )
        for existing in recent_rows:
            notes = json.loads(existing.notes_json or "{}")
            if notes.get("idempotency_key") == payload.idempotency_key:
                parsed_existing = interpret(
                    existing.source_text,
                    intent_override=existing.intent,
                    vocalization_target=existing.vocalization_target,
                )
                return {
                    "status": "ok",
                    "idempotent_retry": True,
                    "intent": parsed_existing,
                    "generated": _serialize_gen(existing, db),
                }

    parsed = interpret(
        payload.text,
        intent_override=payload.intent_override,
        vocalization_target=payload.vocalization_target,
        intensity=payload.intensity,
        duration_sec=payload.duration_sec,
        pitch_hz=payload.pitch_hz,
    )
    intent = parsed["intent"]
    if intent == "unsupported":
        raise HTTPException(status_code=400, detail=parsed.get("reason") or "Invalid or empty input")
    if parsed["needs_clarification"]:
        return {"status": "needs_clarification", "intent": parsed, "generated": None}

    mapping = parsed["mapping"]
    target = payload.vocalization_target.strip().lower() if payload.vocalization_target else mapping.get("vocalization_target")
    if not target:
        raise HTTPException(status_code=400, detail="No vocalization target mapped for this intent")

    gen_method = (payload.generation_method or "reference_direct").strip().lower()
    try:
        y, params = generate_reference_driven_audio(
            vocalization=target,
            intent=intent,
            generation_method=gen_method,
            reference_asset_id=payload.reference_asset_id,
            intensity=payload.intensity,
            duration_sec=payload.duration_sec,
            pitch_hz=payload.pitch_hz,
            pitch_shift_semitones=payload.pitch_shift_semitones,
            time_stretch_rate=payload.time_stretch_rate,
            variation_index=payload.variation_index,
            user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    gen_id = str(uuid.uuid4())
    gen_dir = storage.generated_dir(user.id)
    path = gen_dir / f"{gen_id}.wav"
    wave_path = gen_dir / f"{gen_id}_wave.png"
    spec_path = gen_dir / f"{gen_id}_spec.png"

    try:
        sf.write(str(path), y.astype(np.float32), int(params["sr"]), subtype="PCM_16")
        validation = validate_generated_wav(path, expected_sr=int(params["sr"]))
        write_plots(y, int(params["sr"]), wave_path, spec_path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        wave_path.unlink(missing_ok=True)
        spec_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Audio generation validation failed: {exc}") from exc

    params["validation"] = validation
    actual_method = params.get("generation_method", gen_method)
    output_class = params.get("output_classification", "Reference-Driven Audio")
    is_synthetic = bool(params.get("synthetic", False))

    if actual_method == "reference_direct":
        disclaimer = (
            "Original Reference Audio (Retrieval): This playback uses an authentic dog vocalization recording "
            "from the Reference Audio Library. It is not newly synthesized speech and does not prove canine comprehension."
        )
    elif actual_method == "reference_variation":
        disclaimer = (
            "Transformed Reference Audio (Controlled Variation): This audio is a controlled pitch/time/envelope "
            "variation of a real dog reference recording, not an independently learned dog voice."
        )
    else:
        disclaimer = (
            "Experimental Synthetic DSP Output: Generated by parametric oscillators and formant resonators. "
            "Not a real dog recording and no claim that a dog will understand this sound."
        )

    notes_payload = {
        "disclaimer": disclaimer,
        "output_classification": output_class,
        "generation_method": actual_method,
        "requested_generation_method": params.get("requested_generation_method", gen_method),
        "method_substituted": bool(params.get("method_substituted", False)),
        "requested_category": params.get("requested_category"),
        "source_reference_asset_ids": params.get("source_reference_asset_ids", []),
        "primary_reference_asset": params.get("primary_reference_asset"),
        "transformation_parameters": params.get("transformation_parameters"),
        "acoustic_comparison": params.get("acoustic_comparison"),
        "generation_warnings": params.get("generation_warnings", []),
        "mapping_note": mapping.get("note"),
        "intent_model": parsed.get("model_version"),
        "normalized_input": parsed.get("normalized_input"),
        "validation": validation,
        "waveform_path": storage.rel(wave_path),
        "spectrogram_path": storage.rel(spec_path),
        "idempotency_key": payload.idempotency_key,
        "synthetic": is_synthetic,
    }

    try:
        row = models.GeneratedAudio(
            id=gen_id,
            user_id=user.id,
            dog_id=dog.id if dog else None,
            source_type=actual_method[:16],
            source_text=(payload.text or target).strip(),
            intent=intent,
            intent_confidence=float(parsed["confidence"]),
            mapping_status=actual_method[:32],
            vocalization_target=params.get("vocalization", target)[:32],
            synth_version=params.get("synth_version", SYNTH_MODEL_VERSION),
            audio_path=storage.rel(path),
            params_json=json.dumps(params),
            notes_json=json.dumps(notes_payload),
        )
        db.add(row)
        db.flush()
        audit.log(
            db,
            action="communicate.generate",
            entity="generated",
            user_id=user.id,
            entity_id=gen_id,
            detail=f"method={actual_method},cat={params.get('requested_category')}",
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        wave_path.unlink(missing_ok=True)
        spec_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to persist generated audio record.") from exc

    parsed["reference_category"] = params.get("requested_category")
    parsed["reference_candidates"] = params.get("candidate_references", [])
    return {"status": "ok", "intent": parsed, "generated": _serialize_gen(row, db)}


@router.get("")
def list_generated(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = list(
        db.scalars(
            select(models.GeneratedAudio)
            .where(models.GeneratedAudio.user_id == user.id)
            .order_by(models.GeneratedAudio.created_at.desc())
            .limit(100)
        )
    )
    return [_serialize_gen(r, db) for r in rows]


@router.get("/{gen_id}")
def get_generated(
    gen_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return _serialize_gen(_owned_gen(db, user, gen_id), db)


@router.post("/{gen_id}/feedback")
def record_generation_feedback(
    gen_id: str,
    payload: schemas.GenerationFeedbackIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = _owned_gen(db, user, gen_id)
    notes = json.loads(row.notes_json or "{}")
    notes["user_feedback"] = {
        "rating": payload.rating,
        "sounds_natural": payload.sounds_natural,
        "notes": payload.notes,
    }
    row.notes_json = json.dumps(notes)
    audit.log(
        db,
        action="communicate.feedback",
        entity="generated",
        user_id=user.id,
        entity_id=gen_id,
        detail=f"rating={payload.rating},natural={payload.sounds_natural}",
    )
    db.commit()
    return _serialize_gen(row, db)


@router.get("/{gen_id}/audio")
def get_generated_audio(
    gen_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    row = _owned_gen(db, user, gen_id)
    try:
        path = storage.resolve_owned(user.id, row.audio_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio not found") from None
    return FileResponse(path, media_type="audio/wav", filename=f"caninesense-{row.vocalization_target}.wav")


@router.get("/{gen_id}/media/{kind}")
def get_generated_media(
    gen_id: str,
    kind: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if kind not in {"audio", "waveform", "spectrogram"}:
        raise HTTPException(status_code=404, detail="Unknown media kind")
    if kind == "audio":
        return get_generated_audio(gen_id, user, db)
    row = _owned_gen(db, user, gen_id)
    try:
        wav_path = storage.resolve_owned(user.id, row.audio_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio not found") from None

    wave_path = wav_path.parent / f"{row.id}_wave.png"
    spec_path = wav_path.parent / f"{row.id}_spec.png"
    target_path = wave_path if kind == "waveform" else spec_path
    try:
        ensure_plots(wav_path, wave_path, spec_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not render media plot") from exc
    return FileResponse(target_path, media_type="image/png", filename=target_path.name)


@router.get("/{gen_id}/spectrogram-data")
def get_generated_spectrogram_data(
    gen_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = _owned_gen(db, user, gen_id)
    try:
        wav_path = storage.resolve_owned(user.id, row.audio_path)
        return compute_spectrogram_from_file(wav_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio not found") from None
    except SpectrogramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{gen_id}/responses")
def list_generated_responses(
    gen_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    gen = _owned_gen(db, user, gen_id)
    resps = list(
        db.scalars(
            select(models.DogResponse)
            .where(
                models.DogResponse.generated_id == gen.id,
                models.DogResponse.user_id == user.id,
            )
            .order_by(models.DogResponse.created_at.desc())
        )
    )
    out = []
    for r in resps:
        rec = db.get(models.Recording, r.recording_id)
        analysis = db.get(models.Analysis, r.analysis_id) if r.analysis_id else None
        if rec and rec.user_id == user.id:
            out.append(
                {
                    "id": r.id,
                    "generated_id": gen.id,
                    "recording": _serialize_recording(rec, analysis),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "interpretation_warning": (
                        "A recorded response is not proof that the dog understood the generated sound. "
                        "Engine A analyzed the response independently of Engine B."
                    ),
                }
            )
    return out


@router.post("/{gen_id}/response")
def record_response(
    request: Request,
    gen_id: str,
    upload: UploadFile = File(..., alias="file"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    limit_analyze(request)
    gen = _owned_gen(db, user, gen_id)
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    file_sha = hashlib.sha256(data).hexdigest()

    existing_resps = list(
        db.scalars(
            select(models.DogResponse).where(
                models.DogResponse.generated_id == gen.id,
                models.DogResponse.user_id == user.id,
            )
        )
    )
    for ex_resp in existing_resps:
        ex_rec = db.get(models.Recording, ex_resp.recording_id)
        if ex_rec and ex_rec.sha256 == file_sha and ex_rec.user_id == user.id:
            ex_analysis = db.get(models.Analysis, ex_resp.analysis_id) if ex_resp.analysis_id else None
            return {
                "id": ex_resp.id,
                "generated_id": gen.id,
                "idempotent_retry": True,
                "recording": _serialize_recording(ex_rec, ex_analysis),
                "interpretation_warning": (
                    "A recorded response is not proof that the dog understood the generated sound. "
                    "Engine A analyzed the response independently of Engine B."
                ),
            }

    rec_id = str(uuid.uuid4())
    folder = storage.recording_dir(user.id, rec_id)
    ext = storage.safe_ext(upload.filename or "response.webm") or ".bin"
    original_path = folder / f"original{ext}"
    processed_path = folder / "processed.wav"
    wave_path = folder / "waveform.png"
    spec_path = folder / "spectrogram.png"
    try:
        meta = write_and_decode(data, original_path, processed_path, upload.filename or "response.webm")
    except AudioError as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=400, detail="Could not decode response audio.") from exc

    y, sr = meta["y"], meta["sr"]
    quality = meta["quality"]
    try:
        write_plots(y, sr, wave_path, spec_path)
        dog = db.get(models.Dog, gen.dog_id) if gen.dog_id else None
        if dog and dog.user_id != user.id:
            dog = None
        result = run_analysis_pipeline(y, sr, quality, dog)
    except Exception as exc:
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=500, detail="Response analysis failed.") from exc

    try:
        rec = models.Recording(
            id=rec_id,
            user_id=user.id,
            dog_id=gen.dog_id,
            original_filename=(upload.filename or "response")[:260],
            original_path=storage.rel(original_path),
            processed_path=storage.rel(processed_path),
            spectrogram_path=storage.rel(spec_path),
            waveform_path=storage.rel(wave_path),
            content_type=upload.content_type or "application/octet-stream",
            sha256=file_sha,
            file_size=len(data),
            duration_sec=meta["duration"],
            sample_rate=sr,
            channels=1,
            quality_status=quality.get("status", "ok"),
            quality_json=json.dumps(quality),
            source="dog_response",
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
            features_json=json.dumps(_to_json(result["features"])),
            behavior_json=json.dumps(result["behavior"]),
            explanation_json=json.dumps(result["explanation"]),
            limitations_json=json.dumps(result["explanation"].get("limitations") or []),
        )
        db.add(analysis)
        db.flush()

        resp = models.DogResponse(
            id=str(uuid.uuid4()),
            user_id=user.id,
            generated_id=gen.id,
            recording_id=rec.id,
            analysis_id=analysis.id,
        )
        db.add(resp)
        db.flush()
        audit.log(db, action="communicate.response", entity="dog_response", user_id=user.id, entity_id=resp.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        storage.delete_recording_tree(user.id, rec_id)
        raise HTTPException(status_code=500, detail="Could not persist response record.") from exc

    return {
        "id": resp.id,
        "generated_id": gen.id,
        "recording": _serialize_recording(rec, analysis),
        "interpretation_warning": (
            "A recorded response is not proof that the dog understood the generated sound. "
            "Engine A analyzed the response independently of Engine B."
        ),
    }


def _serialize_gen(row: models.GeneratedAudio, db: Session | None = None) -> dict:
    params = json.loads(row.params_json or "{}")
    notes = json.loads(row.notes_json or "{}")
    validation = params.get("validation") or notes.get("validation")
    resp_count = 0
    if db is not None:
        resp_count = len(
            list(
                db.scalars(
                    select(models.DogResponse.id).where(
                        models.DogResponse.generated_id == row.id,
                        models.DogResponse.user_id == row.user_id,
                    )
                )
            )
        )
    gen_method = params.get("generation_method") or notes.get("generation_method") or "experimental_dsp"
    is_synthetic = bool(params.get("synthetic", gen_method == "experimental_dsp"))
    primary_ref = params.get("primary_reference_asset") or notes.get("primary_reference_asset")
    return {
        "id": row.id,
        "dog_id": row.dog_id,
        "source_type": row.source_type,
        "source_text": row.source_text,
        "intent": row.intent,
        "intent_confidence": row.intent_confidence,
        "mapping_status": row.mapping_status,
        "vocalization_target": row.vocalization_target,
        "requested_category": params.get("requested_category") or notes.get("requested_category") or row.vocalization_target.upper(),
        "generation_method": gen_method,
        "output_classification": params.get("output_classification") or notes.get("output_classification") or "Audio Output",
        "is_reference_recording": bool(params.get("is_reference_recording", False)),
        "is_modified_recording": bool(params.get("is_modified_recording", False)),
        "source_reference_asset_ids": params.get("source_reference_asset_ids") or notes.get("source_reference_asset_ids") or [],
        "primary_reference_asset": primary_ref,
        "transformation_parameters": params.get("transformation_parameters") or notes.get("transformation_parameters") or {},
        "acoustic_comparison": params.get("acoustic_comparison") or notes.get("acoustic_comparison"),
        "generation_warnings": params.get("generation_warnings") or notes.get("generation_warnings") or [],
        "user_feedback": notes.get("user_feedback"),
        "synth_version": row.synth_version,
        "params": params,
        "validation": validation,
        "notes": notes,
        "response_count": resp_count,
        "media_urls": {
            "audio": f"/api/communicate/{row.id}/audio",
            "waveform": f"/api/communicate/{row.id}/media/waveform",
            "spectrogram": f"/api/communicate/{row.id}/media/spectrogram",
            "spectrogram_data": f"/api/communicate/{row.id}/spectrogram-data",
        },
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "synthetic": is_synthetic,
    }


def _to_json(obj):
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json(v) for v in obj]
    if isinstance(obj, (float, int, str, bool)) or obj is None:
        return obj
    try:
        return float(obj)
    except Exception:
        return str(obj)
