"""Dashboard aggregates. Computed from the authenticated user's own rows only."""

from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import BEHAVIOR_MODEL_VERSION, MODEL_VERSION, SYNTH_MODEL_VERSION, models
from ..db import get_db
from ..deps import get_current_user
from ..services import audit, storage

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary")
def summary(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rec_count = db.scalar(
        select(func.count()).select_from(models.Recording).where(models.Recording.user_id == user.id)
    ) or 0
    dog_count = db.scalar(select(func.count()).select_from(models.Dog).where(models.Dog.user_id == user.id)) or 0
    gen_count = db.scalar(
        select(func.count()).select_from(models.GeneratedAudio).where(models.GeneratedAudio.user_id == user.id)
    ) or 0
    analyses = list(db.scalars(select(models.Analysis).where(models.Analysis.user_id == user.id)))
    voc_counter: Counter[str] = Counter()
    abstain = 0
    for a in analyses:
        if a.abstained or a.vocalization == "unknown":
            abstain += 1
        else:
            voc_counter[a.vocalization] += 1
    recent = list(
        db.scalars(
            select(models.Analysis)
            .where(models.Analysis.user_id == user.id)
            .order_by(models.Analysis.created_at.desc())
            .limit(8)
        )
    )
    recent_out = []
    for a in recent:
        rec = db.get(models.Recording, a.recording_id)
        recent_out.append(
            {
                "analysis_id": a.id,
                "recording_id": a.recording_id,
                "dog_id": a.dog_id,
                "vocalization": a.vocalization,
                "confidence": a.confidence,
                "abstained": a.abstained,
                "filename": rec.original_filename if rec else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )
    most = voc_counter.most_common(1)
    return {
        "recordings": rec_count,
        "dogs": dog_count,
        "generated": gen_count,
        "analyses": len(analyses),
        "abstentions": abstain,
        "vocalization_counts": dict(voc_counter),
        "most_frequent_vocalization": most[0][0] if most else None,
        "recent": recent_out,
        "models": {
            "vocalization": MODEL_VERSION,
            "behavior": BEHAVIOR_MODEL_VERSION,
            "synth": SYNTH_MODEL_VERSION,
            "accuracy_target_met": False,
        },
    }


@router.get("/account/export")
def export_data(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    dogs = list(db.scalars(select(models.Dog).where(models.Dog.user_id == user.id)))
    recs = list(db.scalars(select(models.Recording).where(models.Recording.user_id == user.id)))
    ans = list(db.scalars(select(models.Analysis).where(models.Analysis.user_id == user.id)))
    gens = list(db.scalars(select(models.GeneratedAudio).where(models.GeneratedAudio.user_id == user.id)))
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "created_at": user.created_at.isoformat()},
        "dogs": [
            {
                "id": d.id,
                "name": d.name,
                "breed": d.breed,
                "sex": d.sex,
                "age_years": d.age_years,
                "weight_kg": d.weight_kg,
                "notes": d.notes,
            }
            for d in dogs
        ],
        "recordings": [
            {
                "id": r.id,
                "dog_id": r.dog_id,
                "filename": r.original_filename,
                "duration_sec": r.duration_sec,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "source": r.source,
            }
            for r in recs
        ],
        "analyses": [
            {
                "id": a.id,
                "recording_id": a.recording_id,
                "vocalization": a.vocalization,
                "confidence": a.confidence,
                "abstained": a.abstained,
                "behavior": json.loads(a.behavior_json),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in ans
        ],
        "generated": [
            {
                "id": g.id,
                "intent": g.intent,
                "vocalization_target": g.vocalization_target,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in gens
        ],
        "note": "Audio binaries are not inlined. Delete account to remove stored audio.",
    }


@router.delete("/account")
def delete_account(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    uid = user.id
    db.query(models.DogResponse).filter(models.DogResponse.user_id == uid).delete()
    db.query(models.Analysis).filter(models.Analysis.user_id == uid).delete()
    db.query(models.GeneratedAudio).filter(models.GeneratedAudio.user_id == uid).delete()
    db.query(models.Recording).filter(models.Recording.user_id == uid).delete()
    db.query(models.Dog).filter(models.Dog.user_id == uid).delete()
    db.query(models.AuditEvent).filter(models.AuditEvent.user_id == uid).delete()
    db.delete(user)
    db.commit()
    storage.delete_user_tree(uid)
    # Also erase this user's private reference-library uploads (audio + manifest rows).
    from ..services.reference_library import purge_user_references

    purge_user_references(uid)
    return {"ok": True}


@router.get("/models/current")
def current_models() -> dict:
    return {
        "vocalization_model": {
            "id": MODEL_VERSION,
            "type": "literature-informed acoustic membership + softmax",
            "classes": ["bark", "growl", "whine", "howl", "yip", "grunt", "other"],
            "unknown_policy": "abstention when confidence or margin is insufficient",
            "independent_held_out_accuracy": None,
            "target_balanced_accuracy": 0.9,
            "target_met": False,
            "reason_target_unmet": (
                "No sufficiently large, dog-independent, human-annotated evaluation set is present."
            ),
        },
        "behavior_model": {
            "id": BEHAVIOR_MODEL_VERSION,
            "type": "conservative context priors; valence undetermined from audio alone",
        },
        "synth_model": {
            "id": SYNTH_MODEL_VERSION,
            "type": "parametric DSP",
            "dog_comprehension_claimed": False,
        },
    }
