"""
Engine B — Experimental Validation, Behavioural Trials & Scientific Governance Router.
Endpoints for study participants, reproducible cue identity, randomized schedules,
trial logging, blind independent reviews, and scientific metrics computation.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..deps import get_current_user
from ..services import audit
from ..services.synthesis import synthesize
from ..services.trial_service import (
    ACTION_CATEGORIES,
    EXPERIMENTAL_CONDITIONS,
    MAX_PLAYBACK_SPL_DBA,
    OUTCOME_CATEGORIES,
    PROTOCOL_VERSION,
    compute_experimental_metrics,
    export_pseudonymous_research_archive,
    generate_counterbalanced_schedule,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# Pydantic Schemas

class ParticipantIn(BaseModel):
    pseudonym: str = Field(..., min_length=2, max_length=80)
    owner_consent_confirmed: bool = Field(..., description="Informed consent must be explicitly affirmed")
    welfare_review_confirmed: bool = Field(..., description="Animal welfare ethics screening must be affirmed")
    dog_id: str | None = None
    age_years: float | None = None
    breed: str | None = "unknown"
    sex: str | None = "unknown"
    hearing_limitations: str | None = "none_reported"
    mobility_limitations: str | None = "none_reported"
    familiarity_with_target_action: str = "unknown"
    previous_cue_exposure: bool = False
    training_history_notes: str | None = ""
    baseline_behavioural_notes: str | None = ""


class ExperimentalCueIn(BaseModel):
    cue_label: str = Field(..., min_length=2, max_length=120)
    target_intention: str = Field(..., min_length=2, max_length=40)
    target_action_description: str = Field(..., min_length=5)
    action_category: str = Field(..., description="One of: attention, learned_action, object_directed, location_directed, multi_step")
    synthesis_method: str = "method_d_parametric_glottal"
    synthesis_params: dict[str, Any] = Field(default_factory=dict)
    duration_sec: float = Field(default=1.5, ge=0.1, le=10.0)
    peak_spl_dba: float = Field(default=65.0, ge=40.0, le=MAX_PLAYBACK_SPL_DBA)
    f0_hz: float = Field(default=350.0, ge=80.0, le=1200.0)


class ScheduleIn(BaseModel):
    participant_id: str
    cue_id: str
    session_number: int = Field(default=1, ge=1)
    randomization_seed: int | None = None
    total_trials: int = Field(default=10, ge=4, le=16)
    include_familiar_command: bool = True


class TrialIn(BaseModel):
    participant_id: str
    session_id: str = Field(..., min_length=2, max_length=60)
    trial_order_in_session: int = Field(..., ge=1, le=24)
    experimental_condition: str
    cue_id: str | None = None
    schedule_id: str | None = None
    pre_cue_state: str = "resting"
    measured_spl_dba: float = Field(..., ge=30.0, le=MAX_PLAYBACK_SPL_DBA)
    handler_behaviour: str = "neutral_standing_still"
    first_response: str = "none"
    latency_to_orient_ms: float | None = None
    latency_to_action_ms: float | None = None
    outcome_category: str
    alternative_behaviour_notes: str | None = ""
    reinforcement_provided: str = "none"
    environmental_distractions: str = "none"
    ambient_spl_dba: float | None = None
    video_reference_path: str | None = None
    welfare_flags: list[str] = Field(default_factory=list)
    freezing_observed: bool = False
    abort_triggered: bool = False
    abort_reason: str | None = None
    is_valid: bool = True
    exclusion_reason: str | None = None


class TrialPatchIn(BaseModel):
    outcome_category: str | None = None
    latency_to_orient_ms: float | None = None
    latency_to_action_ms: float | None = None
    is_valid: bool | None = None
    exclusion_reason: str | None = None
    correction_note: str = Field(..., min_length=3)


class IndependentReviewIn(BaseModel):
    reviewer_name: str = Field(..., min_length=2, max_length=120)
    is_blind_to_condition: bool = True
    scored_outcome_category: str
    scored_latency_ms: float | None = None
    reviewer_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_notes: str | None = ""


class ReviewerInvitationIn(BaseModel):
    reviewer_email: EmailStr
    permission_scope: str = Field(default="blind_video_review", pattern="^(blind_video_review|unblinded_audit)$")
    is_blind: bool = True
    expires_in_hours: int = Field(default=168, ge=1, le=720)


class InvitationRespondIn(BaseModel):
    decision: str = Field(..., pattern="^(accept|reject)$")


class PreregistrationIn(BaseModel):
    study_title: str = Field(..., min_length=4, max_length=160)
    hypothesis: str = Field(..., min_length=10)
    target_behaviour: str = Field(..., min_length=5)
    success_criteria: dict[str, Any] = Field(default_factory=lambda: {"min_congruence_rate": 0.75, "min_d_ratio": 0.50, "p_alpha": 0.01})
    baseline_measurement_plan: str = Field(..., min_length=5)
    randomization_rule: str = Field(default="Latin-square counterbalanced schedule with <=2 consecutive identical conditions")
    termination_rules: str = Field(default="Abort immediately on >75 dBA, freezing_observed, or >=2 consecutive moderate stress signs")
    missing_data_policy: str = Field(default="Confounded/aborted trials flagged invalid_or_confounded or welfare_terminated; excluded from efficacy numerator but reported in total exclusion rate")
    statistical_analysis_plan: str = Field(default="Repeated-measures binomial & D_ratio evaluation against C1-C3 controls with Cohen's kappa >= 0.80 inter-rater gate")


class AdverseEventIn(BaseModel):
    participant_id: str
    trial_id: str | None = None
    severity: str = Field(..., pattern="^(mild|moderate|severe)$")
    distress_indicators: list[str] = Field(default_factory=list)
    action_taken: str = Field(..., min_length=4)
    session_aborted: bool = True
    vet_followup_notes: str | None = ""


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _active_invitation_for_user(
    db: Session,
    trial_id: str,
    user: models.User,
) -> models.TrialReviewerInvitation | None:
    email_norm = user.email.lower().strip()
    invs = list(
        db.scalars(
            select(models.TrialReviewerInvitation).where(
                models.TrialReviewerInvitation.trial_id == trial_id,
                models.TrialReviewerInvitation.status == "accepted",
                models.TrialReviewerInvitation.revoked_at.is_(None),
            )
        )
    )
    now = datetime.now(timezone.utc)
    for inv in invs:
        if _as_utc(inv.expires_at) <= now:
            continue
        if inv.reviewer_user_id == user.id or inv.reviewer_email.lower().strip() == email_norm:
            return inv
    return None


# Participant Endpoints

@router.post("/participants", status_code=status.HTTP_201_CREATED)
def register_participant(
    payload: ParticipantIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not payload.owner_consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informed owner consent must be explicitly affirmed prior to experimental enrolment.",
        )
    if not payload.welfare_review_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Animal welfare ethics screening must be confirmed prior to study participant registration.",
        )

    if payload.dog_id:
        dog = db.get(models.Dog, payload.dog_id)
        if not dog or dog.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")

    part = models.StudyParticipant(
        id=str(uuid.uuid4()),
        user_id=user.id,
        dog_id=payload.dog_id,
        pseudonym=payload.pseudonym.strip(),
        owner_consent_confirmed=True,
        welfare_review_confirmed=True,
        age_years=payload.age_years,
        breed=(payload.breed or "unknown").strip(),
        sex=(payload.sex or "unknown").strip().lower(),
        hearing_limitations=(payload.hearing_limitations or "none_reported").strip(),
        mobility_limitations=(payload.mobility_limitations or "none_reported").strip(),
        familiarity_with_target_action=payload.familiarity_with_target_action.strip(),
        previous_cue_exposure=payload.previous_cue_exposure,
        training_history_notes=payload.training_history_notes or "",
        baseline_behavioural_notes=payload.baseline_behavioural_notes or "",
    )
    db.add(part)
    db.flush()
    audit.log(db, action="experiment.participant_registered", entity="study_participant", user_id=user.id, entity_id=part.id)
    db.commit()

    return {
        "id": part.id,
        "pseudonym": part.pseudonym,
        "breed": part.breed,
        "sex": part.sex,
        "owner_consent_confirmed": part.owner_consent_confirmed,
        "welfare_review_confirmed": part.welfare_review_confirmed,
        "created_at": part.created_at.isoformat(),
    }


@router.get("/participants")
def list_participants(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(models.StudyParticipant)
        .where(models.StudyParticipant.user_id == user.id)
        .order_by(models.StudyParticipant.created_at.desc())
    )
    participants = list(db.scalars(stmt))
    out = []
    for p in participants:
        out.append({
            "id": p.id,
            "pseudonym": p.pseudonym,
            "breed": p.breed,
            "sex": p.sex,
            "age_years": p.age_years,
            "familiarity_with_target_action": p.familiarity_with_target_action,
            "owner_consent_confirmed": p.owner_consent_confirmed,
            "welfare_review_confirmed": p.welfare_review_confirmed,
            "created_at": p.created_at.isoformat(),
        })
    return out


# Cue Endpoints

@router.post("/cues", status_code=status.HTTP_201_CREATED)
def register_experimental_cue(
    payload: ExperimentalCueIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.peak_spl_dba > MAX_PLAYBACK_SPL_DBA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stimulus peak SPL {payload.peak_spl_dba} dBA exceeds 75.0 dBA veterinary animal welfare hard cap.",
        )
    if payload.action_category not in ACTION_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action category. Must be one of: {list(ACTION_CATEGORIES)}",
        )

    # Synthesize clean reference audio to compute SHA256 and reproducible wave asset
    synth_params = payload.synthesis_params or {
        "f0": payload.f0_hz,
        "formants": [620.0, 1450.0, 2600.0],
        "subharmonic_mix": 0.2,
        "aspiration_mix": 0.15,
        "burst_count": 2,
    }

    try:
        y = synthesize(
            vocal_family="bark" if payload.target_intention in {"come", "attention"} else "growl" if payload.target_intention == "stop" else "yip",
            duration_sec=payload.duration_sec,
            params=synth_params,
        )
    except Exception:
        # Fallback to smooth synthetic audio
        sr = 22050
        t = np.linspace(0, payload.duration_sec, int(sr * payload.duration_sec), endpoint=False)
        y = 0.4 * np.sin(2 * np.pi * payload.f0_hz * t)

    audio_bytes = (y * 32767.0).astype(np.int16).tobytes()
    cue_sha = hashlib.sha256(audio_bytes).hexdigest()

    cue_id = str(uuid.uuid4())
    audio_rel_path = f"cues/{cue_id}.wav"

    cue = models.ExperimentalCue(
        id=cue_id,
        user_id=user.id,
        cue_label=payload.cue_label.strip(),
        target_intention=payload.target_intention.strip().lower(),
        target_action_description=payload.target_action_description.strip(),
        action_category=payload.action_category,
        synthesis_method=payload.synthesis_method,
        synthesis_params_json=json.dumps(synth_params),
        audio_path=audio_rel_path,
        sha256=cue_sha,
        duration_sec=payload.duration_sec,
        peak_spl_dba=payload.peak_spl_dba,
        f0_hz=payload.f0_hz,
        spectral_summary_json=json.dumps({"f0_nominal": payload.f0_hz, "duration": payload.duration_sec}),
        synth_version="EngineB-v2.0-RosenbergFormant",
        cue_version=1,
        is_active=True,
    )
    db.add(cue)
    db.commit()

    return {
        "id": cue.id,
        "cue_label": cue.cue_label,
        "target_intention": cue.target_intention,
        "action_category": cue.action_category,
        "sha256": cue.sha256,
        "f0_hz": cue.f0_hz,
        "peak_spl_dba": cue.peak_spl_dba,
        "synthesis_method": cue.synthesis_method,
        "cue_version": cue.cue_version,
        "created_at": cue.created_at.isoformat(),
    }


@router.get("/cues")
def list_experimental_cues(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    cues = list(db.scalars(select(models.ExperimentalCue).where(models.ExperimentalCue.user_id == user.id)))
    return [
        {
            "id": c.id,
            "cue_label": c.cue_label,
            "target_intention": c.target_intention,
            "action_category": c.action_category,
            "target_action_description": c.target_action_description,
            "f0_hz": c.f0_hz,
            "peak_spl_dba": c.peak_spl_dba,
            "sha256": c.sha256,
            "cue_version": c.cue_version,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat(),
        }
        for c in cues
    ]


# Schedule & Trial Runner Endpoints

@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_randomized_schedule(
    payload: ScheduleIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    part = db.get(models.StudyParticipant, payload.participant_id)
    if not part or part.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    cue = db.get(models.ExperimentalCue, payload.cue_id)
    if not cue or cue.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experimental cue not found")

    seed = payload.randomization_seed if payload.randomization_seed is not None else (secrets.randbelow(900000) + 100000)
    conditions = generate_counterbalanced_schedule(
        seed=seed,
        session_number=payload.session_number,
        total_trials=payload.total_trials,
        include_familiar_command=payload.include_familiar_command,
    )

    sched = models.TrialSchedule(
        id=str(uuid.uuid4()),
        user_id=user.id,
        participant_id=part.id,
        cue_id=cue.id,
        session_number=payload.session_number,
        randomization_seed=seed,
        schedule_type="latin_square_counterbalanced",
        planned_conditions_json=json.dumps(conditions),
        is_completed=False,
    )
    db.add(sched)
    db.commit()

    return {
        "id": sched.id,
        "participant_pseudonym": part.pseudonym,
        "cue_label": cue.cue_label,
        "session_number": sched.session_number,
        "randomization_seed": sched.randomization_seed,
        "planned_conditions": conditions,
        "total_trials": len(conditions),
    }


@router.post("/trials", status_code=status.HTTP_201_CREATED)
def log_behavioural_trial(
    payload: TrialIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    part = db.get(models.StudyParticipant, payload.participant_id)
    if not part or part.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    if payload.cue_id:
        cue = db.get(models.ExperimentalCue, payload.cue_id)
        if not cue or cue.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experimental cue not found")
    if payload.schedule_id:
        sched = db.get(models.TrialSchedule, payload.schedule_id)
        if not sched or sched.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial schedule not found")

    # Volume cap check
    if payload.measured_spl_dba > MAX_PLAYBACK_SPL_DBA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Measured sound level {payload.measured_spl_dba} dBA exceeds 75.0 dBA veterinary animal welfare hard cap.",
        )

    # Valid outcome category check
    outcome = payload.outcome_category
    if payload.abort_triggered:
        outcome = "welfare_terminated"
    elif outcome not in OUTCOME_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid outcome category '{outcome}'. Must be one of: {list(OUTCOME_CATEGORIES)}",
        )

    # Validate condition
    if payload.experimental_condition not in EXPERIMENTAL_CONDITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid experimental condition. Must be one of: {list(EXPERIMENTAL_CONDITIONS)}",
        )

    trial = models.BehaviouralTrial(
        id=str(uuid.uuid4()),
        user_id=user.id,
        participant_id=part.id,
        schedule_id=payload.schedule_id,
        session_id=payload.session_id.strip(),
        trial_order_in_session=payload.trial_order_in_session,
        experimental_condition=payload.experimental_condition,
        cue_id=payload.cue_id,
        pre_cue_state=payload.pre_cue_state,
        measured_spl_dba=payload.measured_spl_dba,
        handler_behaviour=payload.handler_behaviour,
        first_response=payload.first_response,
        latency_to_orient_ms=payload.latency_to_orient_ms,
        latency_to_action_ms=payload.latency_to_action_ms,
        outcome_category=outcome,
        alternative_behaviour_notes=payload.alternative_behaviour_notes or "",
        reinforcement_provided=payload.reinforcement_provided,
        environmental_distractions=payload.environmental_distractions,
        ambient_spl_dba=payload.ambient_spl_dba,
        video_reference_path=payload.video_reference_path,
        welfare_flags_json=json.dumps(payload.welfare_flags or []),
        freezing_observed=payload.freezing_observed,
        abort_triggered=payload.abort_triggered,
        abort_reason=payload.abort_reason,
        is_valid=payload.is_valid,
        exclusion_reason=payload.exclusion_reason,
        observer_user_id=user.id,
        correction_audit_json="[]",
    )
    db.add(trial)
    db.commit()

    return {
        "id": trial.id,
        "participant_id": trial.participant_id,
        "session_id": trial.session_id,
        "trial_order": trial.trial_order_in_session,
        "experimental_condition": trial.experimental_condition,
        "outcome_category": trial.outcome_category,
        "latency_to_action_ms": trial.latency_to_action_ms,
        "is_valid": trial.is_valid,
        "welfare_warning": (
            "Freezing/quiescence detected: do not assume silence indicates calm state."
            if trial.freezing_observed
            else None
        ),
        "created_at": trial.created_at.isoformat(),
    }


@router.get("/trials")
def list_trials(
    participant_id: str | None = None,
    session_id: str | None = None,
    condition: str | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(models.BehaviouralTrial).where(models.BehaviouralTrial.user_id == user.id)
    if participant_id:
        stmt = stmt.where(models.BehaviouralTrial.participant_id == participant_id)
    if session_id:
        stmt = stmt.where(models.BehaviouralTrial.session_id == session_id)
    if condition:
        stmt = stmt.where(models.BehaviouralTrial.experimental_condition == condition)

    trials = list(db.scalars(stmt.order_by(models.BehaviouralTrial.playback_timestamp.desc()).limit(300)))
    return [
        {
            "id": t.id,
            "participant_id": t.participant_id,
            "session_id": t.session_id,
            "trial_order": t.trial_order_in_session,
            "experimental_condition": t.experimental_condition,
            "outcome_category": t.outcome_category,
            "latency_to_orient_ms": t.latency_to_orient_ms,
            "latency_to_action_ms": t.latency_to_action_ms,
            "measured_spl_dba": t.measured_spl_dba,
            "freezing_observed": t.freezing_observed,
            "abort_triggered": t.abort_triggered,
            "is_valid": t.is_valid,
            "created_at": t.created_at.isoformat(),
        }
        for t in trials
    ]


@router.patch("/trials/{trial_id}")
def correct_trial_record(
    trial_id: str,
    payload: TrialPatchIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    trial = db.get(models.BehaviouralTrial, trial_id)
    if not trial or trial.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")

    # Append auditable correction record
    audits = json.loads(trial.correction_audit_json or "[]")
    diff: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "corrected_by_user_id": user.id,
        "note": payload.correction_note,
        "changes": {},
    }

    if payload.outcome_category is not None:
        if payload.outcome_category not in OUTCOME_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid outcome category")
        diff["changes"]["outcome_category"] = {"old": trial.outcome_category, "new": payload.outcome_category}
        trial.outcome_category = payload.outcome_category

    if payload.latency_to_orient_ms is not None:
        diff["changes"]["latency_to_orient_ms"] = {"old": trial.latency_to_orient_ms, "new": payload.latency_to_orient_ms}
        trial.latency_to_orient_ms = payload.latency_to_orient_ms

    if payload.latency_to_action_ms is not None:
        diff["changes"]["latency_to_action_ms"] = {"old": trial.latency_to_action_ms, "new": payload.latency_to_action_ms}
        trial.latency_to_action_ms = payload.latency_to_action_ms

    if payload.is_valid is not None:
        diff["changes"]["is_valid"] = {"old": trial.is_valid, "new": payload.is_valid}
        trial.is_valid = payload.is_valid

    if payload.exclusion_reason is not None:
        diff["changes"]["exclusion_reason"] = {"old": trial.exclusion_reason, "new": payload.exclusion_reason}
        trial.exclusion_reason = payload.exclusion_reason

    audits.append(diff)
    trial.correction_audit_json = json.dumps(audits)
    trial.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": trial.id,
        "outcome_category": trial.outcome_category,
        "is_valid": trial.is_valid,
        "correction_count": len(audits),
        "updated_at": trial.updated_at.isoformat(),
    }


# Independent Reviewer Invitation & Blind Authorization Endpoints

@router.post("/trials/{trial_id}/invitations", status_code=status.HTTP_201_CREATED)
def invite_independent_reviewer(
    trial_id: str,
    payload: ReviewerInvitationIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    trial = db.get(models.BehaviouralTrial, trial_id)
    if not trial or trial.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")

    target_email = str(payload.reviewer_email).lower().strip()
    if target_email == user.email.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Independent reviewer must be a separate account from the trial owner.",
        )

    invited_user = db.scalar(select(models.User).where(models.User.email == target_email))
    now = datetime.now(timezone.utc)
    inv = models.TrialReviewerInvitation(
        id=str(uuid.uuid4()),
        trial_id=trial.id,
        study_owner_user_id=user.id,
        invited_by_user_id=user.id,
        reviewer_email=target_email,
        reviewer_user_id=invited_user.id if invited_user else None,
        permission_scope=payload.permission_scope,
        is_blind=bool(payload.is_blind),
        status="pending",
        expires_at=now + timedelta(hours=payload.expires_in_hours),
    )
    db.add(inv)
    db.flush()
    audit.log(
        db,
        action="experiment.reviewer_invited",
        entity="trial_reviewer_invitation",
        user_id=user.id,
        entity_id=inv.id,
        detail=f"trial={trial.id},scope={inv.permission_scope},blind={inv.is_blind}",
    )
    db.commit()
    return {
        "id": inv.id,
        "trial_id": inv.trial_id,
        "reviewer_email": inv.reviewer_email,
        "permission_scope": inv.permission_scope,
        "is_blind": inv.is_blind,
        "status": inv.status,
        "expires_at": _as_utc(inv.expires_at).isoformat(),
        "created_at": _as_utc(inv.created_at).isoformat(),
    }


@router.get("/invitations")
def list_reviewer_invitations(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    email_norm = user.email.lower().strip()
    now = datetime.now(timezone.utc)

    incoming_rows = list(
        db.scalars(
            select(models.TrialReviewerInvitation)
            .where(
                (models.TrialReviewerInvitation.reviewer_user_id == user.id)
                | (models.TrialReviewerInvitation.reviewer_email == email_norm)
            )
            .order_by(models.TrialReviewerInvitation.created_at.desc())
        )
    )
    outgoing_rows = list(
        db.scalars(
            select(models.TrialReviewerInvitation)
            .where(models.TrialReviewerInvitation.study_owner_user_id == user.id)
            .order_by(models.TrialReviewerInvitation.created_at.desc())
        )
    )

    def _serialize(inv: models.TrialReviewerInvitation, include_email: bool) -> dict[str, Any]:
        exp = _as_utc(inv.expires_at)
        effective_status = "expired" if (inv.status in {"pending", "accepted"} and exp <= now and inv.revoked_at is None) else inv.status
        out: dict[str, Any] = {
            "id": inv.id,
            "trial_id": inv.trial_id,
            "permission_scope": inv.permission_scope,
            "is_blind": inv.is_blind,
            "status": effective_status,
            "expires_at": exp.isoformat(),
            "created_at": _as_utc(inv.created_at).isoformat(),
        }
        if include_email:
            out["reviewer_email"] = inv.reviewer_email
        return out

    return {
        "incoming": [_serialize(i, include_email=False) for i in incoming_rows],
        "outgoing": [_serialize(i, include_email=True) for i in outgoing_rows],
    }


@router.post("/invitations/{invitation_id}/respond")
def respond_reviewer_invitation(
    invitation_id: str,
    payload: InvitationRespondIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    inv = db.get(models.TrialReviewerInvitation, invitation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    email_norm = user.email.lower().strip()
    if inv.reviewer_email.lower().strip() != email_norm and inv.reviewer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to respond to this invitation")

    if inv.revoked_at is not None or inv.status == "revoked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation has been revoked")

    now = datetime.now(timezone.utc)
    if _as_utc(inv.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation has expired")

    if inv.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invitation already {inv.status}")

    inv.reviewer_user_id = user.id
    inv.status = "accepted" if payload.decision == "accept" else "rejected"
    inv.responded_at = now
    audit.log(
        db,
        action=f"experiment.reviewer_{inv.status}",
        entity="trial_reviewer_invitation",
        user_id=user.id,
        entity_id=inv.id,
        detail=f"trial={inv.trial_id}",
    )
    db.commit()
    return {"id": inv.id, "trial_id": inv.trial_id, "status": inv.status, "is_blind": inv.is_blind}


@router.post("/invitations/{invitation_id}/revoke")
def revoke_reviewer_invitation(
    invitation_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    inv = db.get(models.TrialReviewerInvitation, invitation_id)
    if not inv or inv.study_owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    inv.status = "revoked"
    inv.revoked_at = datetime.now(timezone.utc)
    audit.log(
        db,
        action="experiment.reviewer_revoked",
        entity="trial_reviewer_invitation",
        user_id=user.id,
        entity_id=inv.id,
        detail=f"trial={inv.trial_id}",
    )
    db.commit()
    return {"id": inv.id, "trial_id": inv.trial_id, "status": inv.status}


@router.get("/assigned-trials")
def list_assigned_trials_for_reviewer(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    email_norm = user.email.lower().strip()
    now = datetime.now(timezone.utc)
    invs = list(
        db.scalars(
            select(models.TrialReviewerInvitation).where(
                models.TrialReviewerInvitation.status == "accepted",
                models.TrialReviewerInvitation.revoked_at.is_(None),
                (models.TrialReviewerInvitation.reviewer_user_id == user.id)
                | (models.TrialReviewerInvitation.reviewer_email == email_norm),
            )
        )
    )
    out = []
    for inv in invs:
        if _as_utc(inv.expires_at) <= now:
            continue
        trial = db.get(models.BehaviouralTrial, inv.trial_id)
        if not trial:
            continue
        item: dict[str, Any] = {
            "invitation_id": inv.id,
            "trial_id": trial.id,
            "session_id": trial.session_id,
            "trial_order": trial.trial_order_in_session,
            "pre_cue_state": trial.pre_cue_state,
            "video_reference_path": trial.video_reference_path,
            "is_blind": inv.is_blind,
            "permission_scope": inv.permission_scope,
            "created_at": trial.created_at.isoformat(),
        }
        # Only expose condition/primary outcome if explicitly unblinded assignment
        if not inv.is_blind:
            item["experimental_condition"] = trial.experimental_condition
            item["primary_outcome_category"] = trial.outcome_category
        out.append(item)
    return out


# Independent Reviewer Endpoints

@router.post("/trials/{trial_id}/reviews", status_code=status.HTTP_201_CREATED)
def submit_independent_review(
    trial_id: str,
    payload: IndependentReviewIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    trial = db.get(models.BehaviouralTrial, trial_id)
    if not trial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")

    if trial.user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Primary study owner cannot submit an independent review for their own trial.",
        )

    inv = _active_invitation_for_user(db, trial.id, user)
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explicit accepted reviewer invitation required to review this trial.",
        )

    if payload.scored_outcome_category not in OUTCOME_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid outcome category")

    # Prevent duplicate reviews from the same reviewer account
    existing = db.scalar(
        select(models.TrialIndependentReview).where(
            models.TrialIndependentReview.trial_id == trial.id,
            models.TrialIndependentReview.reviewer_user_id == user.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reviewer has already submitted an evaluation for this trial record.",
        )

    disagreement = payload.scored_outcome_category != trial.outcome_category
    blind_flag = True if inv.is_blind else payload.is_blind_to_condition

    rev = models.TrialIndependentReview(
        id=str(uuid.uuid4()),
        trial_id=trial.id,
        reviewer_user_id=user.id,
        reviewer_name=payload.reviewer_name.strip(),
        is_blind_to_condition=blind_flag,
        scored_outcome_category=payload.scored_outcome_category,
        scored_latency_ms=payload.scored_latency_ms,
        reviewer_confidence=payload.reviewer_confidence,
        review_notes=payload.review_notes or "",
        disagreement_with_primary=disagreement,
    )
    db.add(rev)
    db.flush()
    audit.log(
        db,
        action="experiment.review_submitted",
        entity="trial_independent_review",
        user_id=user.id,
        entity_id=rev.id,
        detail=f"trial={trial.id},blind={blind_flag}",
    )
    db.commit()

    resp: dict[str, Any] = {
        "id": rev.id,
        "trial_id": rev.trial_id,
        "reviewer_name": rev.reviewer_name,
        "scored_outcome_category": rev.scored_outcome_category,
        "is_blind_to_condition": blind_flag,
        "created_at": rev.created_at.isoformat(),
    }
    if not blind_flag:
        resp["disagreement_with_primary"] = disagreement
        resp["primary_observer_category"] = trial.outcome_category
    return resp


@router.get("/trials/{trial_id}/reviews")
def list_trial_reviews_for_owner(
    trial_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    trial = db.get(models.BehaviouralTrial, trial_id)
    if not trial or trial.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")
    revs = list(
        db.scalars(
            select(models.TrialIndependentReview)
            .where(models.TrialIndependentReview.trial_id == trial.id)
            .order_by(models.TrialIndependentReview.created_at.desc())
        )
    )
    return [
        {
            "id": r.id,
            "trial_id": r.trial_id,
            "reviewer_name": r.reviewer_name,
            "is_blind_to_condition": r.is_blind_to_condition,
            "scored_outcome_category": r.scored_outcome_category,
            "disagreement_with_primary": r.disagreement_with_primary,
            "reviewer_confidence": r.reviewer_confidence,
            "review_notes": r.review_notes,
            "created_at": r.created_at.isoformat(),
        }
        for r in revs
    ]


# Preregistration & Adverse Events (Priority D Trial Readiness)

@router.post("/preregistrations", status_code=status.HTTP_201_CREATED)
def create_preregistration(
    payload: PreregistrationIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    pre = models.TrialPreregistration(
        id=str(uuid.uuid4()),
        user_id=user.id,
        study_title=payload.study_title.strip(),
        hypothesis=payload.hypothesis.strip(),
        target_behaviour=payload.target_behaviour.strip(),
        success_criteria_json=json.dumps(payload.success_criteria),
        baseline_measurement_plan=payload.baseline_measurement_plan.strip(),
        randomization_rule=payload.randomization_rule.strip(),
        termination_rules=payload.termination_rules.strip(),
        missing_data_policy=payload.missing_data_policy.strip(),
        statistical_analysis_plan=payload.statistical_analysis_plan.strip(),
        protocol_version=PROTOCOL_VERSION,
    )
    db.add(pre)
    db.flush()
    audit.log(db, action="experiment.preregistered", entity="trial_preregistration", user_id=user.id, entity_id=pre.id)
    db.commit()
    return {
        "id": pre.id,
        "study_title": pre.study_title,
        "hypothesis": pre.hypothesis,
        "target_behaviour": pre.target_behaviour,
        "success_criteria": payload.success_criteria,
        "protocol_version": pre.protocol_version,
        "locked_at": _as_utc(pre.locked_at).isoformat(),
    }


@router.get("/preregistrations")
def list_preregistrations(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(models.TrialPreregistration)
            .where(models.TrialPreregistration.user_id == user.id)
            .order_by(models.TrialPreregistration.locked_at.desc())
        )
    )
    return [
        {
            "id": r.id,
            "study_title": r.study_title,
            "hypothesis": r.hypothesis,
            "target_behaviour": r.target_behaviour,
            "success_criteria": json.loads(r.success_criteria_json or "{}"),
            "baseline_measurement_plan": r.baseline_measurement_plan,
            "randomization_rule": r.randomization_rule,
            "termination_rules": r.termination_rules,
            "missing_data_policy": r.missing_data_policy,
            "statistical_analysis_plan": r.statistical_analysis_plan,
            "protocol_version": r.protocol_version,
            "locked_at": _as_utc(r.locked_at).isoformat(),
        }
        for r in rows
    ]


@router.post("/adverse-events", status_code=status.HTTP_201_CREATED)
def log_adverse_event(
    payload: AdverseEventIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    part = db.get(models.StudyParticipant, payload.participant_id)
    if not part or part.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    if payload.trial_id:
        tr = db.get(models.BehaviouralTrial, payload.trial_id)
        if not tr or tr.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")

    ae = models.TrialAdverseEvent(
        id=str(uuid.uuid4()),
        user_id=user.id,
        participant_id=part.id,
        trial_id=payload.trial_id,
        severity=payload.severity,
        distress_indicators_json=json.dumps(payload.distress_indicators or []),
        action_taken=payload.action_taken.strip(),
        session_aborted=payload.session_aborted,
        vet_followup_notes=(payload.vet_followup_notes or "").strip(),
    )
    db.add(ae)
    db.flush()
    audit.log(db, action="experiment.adverse_event", entity="trial_adverse_event", user_id=user.id, entity_id=ae.id)
    db.commit()
    return {
        "id": ae.id,
        "participant_id": ae.participant_id,
        "trial_id": ae.trial_id,
        "severity": ae.severity,
        "distress_indicators": payload.distress_indicators,
        "action_taken": ae.action_taken,
        "session_aborted": ae.session_aborted,
        "created_at": _as_utc(ae.created_at).isoformat(),
    }


@router.get("/adverse-events")
def list_adverse_events(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(models.TrialAdverseEvent)
            .where(models.TrialAdverseEvent.user_id == user.id)
            .order_by(models.TrialAdverseEvent.created_at.desc())
        )
    )
    return [
        {
            "id": r.id,
            "participant_id": r.participant_id,
            "trial_id": r.trial_id,
            "severity": r.severity,
            "distress_indicators": json.loads(r.distress_indicators_json or "[]"),
            "action_taken": r.action_taken,
            "session_aborted": r.session_aborted,
            "vet_followup_notes": r.vet_followup_notes,
            "created_at": _as_utc(r.created_at).isoformat(),
        }
        for r in rows
    ]


# Scientific Metrics & Research Exports

@router.get("/metrics")
def get_experimental_metrics(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    trials = list(db.scalars(select(models.BehaviouralTrial).where(models.BehaviouralTrial.user_id == user.id)))
    trial_ids = [t.id for t in trials]
    reviews = (
        list(db.scalars(select(models.TrialIndependentReview).where(models.TrialIndependentReview.trial_id.in_(trial_ids))))
        if trial_ids
        else []
    )
    adverse_count = len(list(db.scalars(select(models.TrialAdverseEvent).where(models.TrialAdverseEvent.user_id == user.id))))
    return compute_experimental_metrics(trials, reviews=reviews, adverse_events_count=adverse_count)


@router.get("/export")
def export_research_data(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    content, media_type = export_pseudonymous_research_archive(db, user, format_type=format)
    filename = f"caninesense_research_export_{user.id[:8]}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
