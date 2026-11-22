"""Dashboard aggregates. Computed from the authenticated user's own rows only."""

from __future__ import annotations

import json
import logging
from collections import Counter

import numpy as np
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

log = logging.getLogger("caninesense.analytics")

from .. import BEHAVIOR_MODEL_VERSION, MODEL_VERSION, SYNTH_MODEL_VERSION, models
from ..db import get_db
from ..deps import get_current_user
from ..ml.evaluate import CANONICAL_6_CLASSES, evaluate_dog_independent_generalization
from ..security import revoke_token
from ..services import storage
from ..services.breed_intelligence import resolve_breed_intelligence
from ..services.inference import is_accuracy_target_met

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
    recent_rec_ids = [a.recording_id for a in recent if a.recording_id]
    recs_by_id = (
        {
            r.id: r
            for r in db.scalars(select(models.Recording).where(models.Recording.id.in_(recent_rec_ids)))
        }
        if recent_rec_ids
        else {}
    )
    recent_out = []
    for a in recent:
        rec = recs_by_id.get(a.recording_id)
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
            "accuracy_target_met": is_accuracy_target_met(),
        },
    }


@router.get("/analytics/validation-card")
def validation_card(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Expose 6-class dataset coverage, unique dog ratio, individual dog F0 baselines, and calibration metrics."""
    dogs = list(db.scalars(select(models.Dog).where(models.Dog.user_id == user.id)))
    recs = list(db.scalars(select(models.Recording).where(models.Recording.user_id == user.id)))
    analyses = list(db.scalars(select(models.Analysis).where(models.Analysis.user_id == user.id)))

    class_counts: dict[str, int] = {c: 0 for c in CANONICAL_6_CLASSES}
    for a in analyses:
        lbl = "unknown" if a.abstained else str(a.vocalization or "").strip().lower()
        if lbl not in {"bark", "growl", "whine", "howl", "yip"}:
            lbl = "unknown"
        class_counts[lbl] += 1

    unique_dog_ids_recorded = len({r.dog_id for r in recs if r.dog_id})
    total_recordings = len(recs)
    unique_dogs_to_recordings_ratio = (
        round(unique_dog_ids_recorded / total_recordings, 4) if total_recordings > 0 else 0.0
    )

    dog_baselines: list[dict] = []
    for dog in dogs:
        f0s: list[float] = []
        for a in analyses:
            if a.dog_id != dog.id:
                continue
            try:
                feats = json.loads(a.features_json or "{}")
                val = feats.get("f0_mean")
                if val is not None and np.isfinite(float(val)) and float(val) > 0:
                    f0s.append(float(val))
            except Exception:
                log.warning("Failed parsing features_json for analysis %s", a.id, exc_info=True)

        intel = resolve_breed_intelligence(dog.breed, dog.weight_kg, dog.age_years, sex=dog.sex)
        prior_f0_range = list(intel["vocalization_profile"]["f0_range_hz"])
        if len(f0s) >= 1:
            personal_mean_f0_hz = round(float(np.mean(f0s)), 1)
            personal_std_f0_hz = round(float(np.std(f0s, ddof=0)), 1) if len(f0s) >= 2 else 25.0
        else:
            personal_mean_f0_hz = round((prior_f0_range[0] + prior_f0_range[1]) / 2.0, 1)
            personal_std_f0_hz = round((prior_f0_range[1] - prior_f0_range[0]) / 2.0, 1)

        dog_baselines.append(
            {
                "dog_id": dog.id,
                "dog_name": dog.name,
                "breed": dog.breed or "Mixed",
                "sex": dog.sex or "unknown",
                "sample_count": len(f0s),
                "adaptation_active": len(f0s) >= 1,
                "adaptation_mode": (
                    "individual_dog_historical_baseline" if len(f0s) >= 1 else "breed_sex_allometric_prior"
                ),
                "personal_mean_f0_hz": personal_mean_f0_hz,
                "personal_std_f0_hz": personal_std_f0_hz,
                "personal_f0_band_hz": [
                    round(personal_mean_f0_hz - personal_std_f0_hz, 1),
                    round(personal_mean_f0_hz + personal_std_f0_hz, 1),
                ],
                "static_breed_f0_range_hz": prior_f0_range,
            }
        )

    rec_by_id = {r.id: r for r in recs}
    eval_records: list[dict] = []
    for a in analyses:
        r = rec_by_id.get(a.recording_id)
        q: dict = {}
        if r and r.quality_json:
            try:
                q = json.loads(r.quality_json)
            except Exception:
                log.warning("Failed parsing quality_json for recording %s", r.id, exc_info=True)
                q = {}
        cons_lbl = q.get("consensus_label")
        anns = q.get("independent_annotations") or []
        human_lbl = (
            cons_lbl
            if cons_lbl and cons_lbl != "disputed"
            else (anns[0].get("vocalization_label") if anns else None)
        )
        # Never manufacture self-referential ground truth from unannotated model predictions.
        if not human_lbl:
            continue
        resolved_path = ""
        if r and r.processed_path:
            try:
                resolved_path = str(storage.resolve_owned(user.id, r.processed_path))
            except Exception:
                log.warning("Unable to resolve processed_path for recording %s", r.id, exc_info=True)
                resolved_path = ""
        eval_records.append(
            {
                "dog_id": a.dog_id or (r.dog_id if r else None) or f"rec_{a.recording_id}",
                "label": human_lbl,
                "pred_label": a.vocalization,
                "confidence": a.confidence,
                "abstained": a.abstained,
                "path": resolved_path,
                "is_fixture": False,
            }
        )

    generalization = evaluate_dog_independent_generalization(eval_records)
    return {
        "classes": list(CANONICAL_6_CLASSES),
        "class_counts": class_counts,
        "total_recordings": total_recordings,
        "total_analyses": len(analyses),
        "unique_dog_count": unique_dog_ids_recorded,
        "unique_dog_ids_recorded": unique_dog_ids_recorded,
        "total_dog_profiles": len(dogs),
        "unique_dogs_to_recordings_ratio": unique_dogs_to_recordings_ratio,
        "dog_baselines": dog_baselines,
        "generalization_calibration": generalization,
    }


@router.get("/account/export")
def export_data(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    dogs = list(db.scalars(select(models.Dog).where(models.Dog.user_id == user.id)))
    recs = list(db.scalars(select(models.Recording).where(models.Recording.user_id == user.id)))
    ans = list(db.scalars(select(models.Analysis).where(models.Analysis.user_id == user.id)))
    gens = list(db.scalars(select(models.GeneratedAudio).where(models.GeneratedAudio.user_id == user.id)))
    participants = list(db.scalars(select(models.StudyParticipant).where(models.StudyParticipant.user_id == user.id)))
    cues = list(db.scalars(select(models.ExperimentalCue).where(models.ExperimentalCue.user_id == user.id)))
    schedules = list(db.scalars(select(models.TrialSchedule).where(models.TrialSchedule.user_id == user.id)))
    trials = list(db.scalars(select(models.BehaviouralTrial).where(models.BehaviouralTrial.user_id == user.id)))
    reviews = list(
        db.scalars(
            select(models.TrialIndependentReview).where(models.TrialIndependentReview.reviewer_user_id == user.id)
        )
    )
    preregistrations = list(
        db.scalars(select(models.TrialPreregistration).where(models.TrialPreregistration.user_id == user.id))
    )
    adverse_events = list(db.scalars(select(models.TrialAdverseEvent).where(models.TrialAdverseEvent.user_id == user.id)))
    blind_subs = list(
        db.scalars(select(models.BlindListeningSubmission).where(models.BlindListeningSubmission.user_id == user.id))
    )
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
        "study_participants": [
            {
                "id": p.id,
                "pseudonym": p.pseudonym,
                "breed": p.breed,
                "sex": p.sex,
                "owner_consent_confirmed": p.owner_consent_confirmed,
                "welfare_review_confirmed": p.welfare_review_confirmed,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in participants
        ],
        "experimental_cues": [
            {
                "id": c.id,
                "cue_label": c.cue_label,
                "target_intention": c.target_intention,
                "action_category": c.action_category,
                "peak_spl_dba": c.peak_spl_dba,
                "sha256": c.sha256,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cues
        ],
        "trial_schedules": [
            {
                "id": s.id,
                "participant_id": s.participant_id,
                "cue_id": s.cue_id,
                "session_number": s.session_number,
                "planned_conditions": json.loads(s.planned_conditions_json or "[]"),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in schedules
        ],
        "behavioural_trials": [
            {
                "id": t.id,
                "participant_id": t.participant_id,
                "session_id": t.session_id,
                "experimental_condition": t.experimental_condition,
                "outcome_category": t.outcome_category,
                "measured_spl_dba": t.measured_spl_dba,
                "freezing_observed": t.freezing_observed,
                "abort_triggered": t.abort_triggered,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trials
        ],
        "trial_independent_reviews": [
            {
                "id": rev.id,
                "trial_id": rev.trial_id,
                "scored_outcome_category": rev.scored_outcome_category,
                "is_blind_to_condition": rev.is_blind_to_condition,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            }
            for rev in reviews
        ],
        "trial_preregistrations": [
            {
                "id": pr.id,
                "study_title": pr.study_title,
                "protocol_version": pr.protocol_version,
                "locked_at": pr.locked_at.isoformat() if pr.locked_at else None,
            }
            for pr in preregistrations
        ],
        "trial_adverse_events": [
            {
                "id": ae.id,
                "participant_id": ae.participant_id,
                "severity": ae.severity,
                "session_aborted": ae.session_aborted,
                "created_at": ae.created_at.isoformat() if ae.created_at else None,
            }
            for ae in adverse_events
        ],
        "blind_listening_submissions": [
            {
                "id": b.id,
                "sample_id": b.sample_id,
                "blind_code": b.blind_code,
                "perceived_category": b.perceived_category,
                "naturalness_score": b.naturalness_score,
                "artifact_severity_score": b.artifact_severity_score,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in blind_subs
        ],
        "note": "Audio binaries are not inlined. Delete account to remove stored audio.",
    }


@router.delete("/account")
def delete_account(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Full user erasure: removes DB entities, stored files, private references, and revokes the caller JWT."""
    uid = user.id
    # Durable backends: purge every remote object first so a bucket failure surfaces (503) and is retryable.
    storage.purge_remote_user_tree(uid)
    user_trial_ids = select(models.BehaviouralTrial.id).where(models.BehaviouralTrial.user_id == uid)
    db.query(models.BlindListeningSubmission).filter(models.BlindListeningSubmission.user_id == uid).delete()
    db.query(models.TrialReviewerInvitation).filter(
        (models.TrialReviewerInvitation.study_owner_user_id == uid)
        | (models.TrialReviewerInvitation.invited_by_user_id == uid)
        | (models.TrialReviewerInvitation.reviewer_user_id == uid)
        | (models.TrialReviewerInvitation.trial_id.in_(user_trial_ids))
    ).delete(synchronize_session=False)
    db.query(models.TrialAdverseEvent).filter(models.TrialAdverseEvent.user_id == uid).delete()
    db.query(models.TrialPreregistration).filter(models.TrialPreregistration.user_id == uid).delete()
    db.query(models.TrialIndependentReview).filter(
        (models.TrialIndependentReview.reviewer_user_id == uid)
        | (models.TrialIndependentReview.trial_id.in_(user_trial_ids))
    ).delete(synchronize_session=False)
    db.query(models.BehaviouralTrial).filter(models.BehaviouralTrial.user_id == uid).delete()
    db.query(models.TrialSchedule).filter(models.TrialSchedule.user_id == uid).delete()
    db.query(models.ExperimentalCue).filter(models.ExperimentalCue.user_id == uid).delete()
    db.query(models.StudyParticipant).filter(models.StudyParticipant.user_id == uid).delete()
    db.query(models.DogResponse).filter(models.DogResponse.user_id == uid).delete()
    db.query(models.Analysis).filter(models.Analysis.user_id == uid).delete()
    db.query(models.GeneratedAudio).filter(models.GeneratedAudio.user_id == uid).delete()
    db.query(models.Recording).filter(models.Recording.user_id == uid).delete()
    db.query(models.Dog).filter(models.Dog.user_id == uid).delete()
    db.query(models.AuditEvent).filter(models.AuditEvent.user_id == uid).delete()
    db.delete(user)
    db.commit()
    storage.delete_user_tree(uid, include_remote=False)
    # Also erase this user's private reference-library uploads (audio + manifest rows).
    from ..services.reference_library import purge_user_references

    purge_user_references(uid)
    token = getattr(request.state, "access_token", None)
    if token:
        revoke_token(token)
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
