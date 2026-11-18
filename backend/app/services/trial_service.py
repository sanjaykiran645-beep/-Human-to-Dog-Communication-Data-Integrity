"""
Engine B — Experimental Validation, Behavioural Trial Logging & Scientific Metrics Service.
Provides randomized counterbalanced trial schedules, strict welfare controls (75 dBA cap),
blind video review scoring, and repeated-measures behavioural metrics.
"""

from __future__ import annotations

import csv
import io
import json
import math
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .synthesis import _two_pole_resonator

MAX_PLAYBACK_SPL_DBA = 75.0
PROTOCOL_VERSION = "2.0.0-csai-ethology"

EXPERIMENTAL_CONDITIONS = (
    "target_engine_b_cue",
    "control_silent_baseline",
    "control_neutral_pure_tone",
    "control_spectrally_matched_noise",
    "control_familiar_human_verbal_command",
)

OUTCOME_CATEGORIES = (
    "correct_target_action",
    "attention_only",
    "incorrect_action",
    "alternative_behaviour",
    "no_observable_response",
    "invalid_or_confounded",
    "welfare_terminated",
)

ACTION_CATEGORIES = (
    "attention",
    "learned_action",
    "object_directed",
    "location_directed",
    "multi_step",
)

WELFARE_DISTRESS_INDICATORS = (
    "lip_licking",
    "yawning",
    "paw_lifting",
    "body_shake_off",
    "lowered_tail",
    "whale_eye",
    "crouching",
    "trembling",
    "pacing",
    "defensive_snarl",
)


def generate_counterbalanced_schedule(
    seed: int,
    session_number: int,
    total_trials: int = 10,
    include_familiar_command: bool = True,
) -> list[str]:
    """
    Generate a balanced, counterbalanced trial sequence interleaving the target cue
    with control conditions (C1: Silent, C2: Neutral tone, C3: Matched noise, C4: Familiar command).
    Prevents runs of more than 2 identical conditions.
    """
    rng = random.Random(seed + session_number * 1000)
    controls = [
        "control_silent_baseline",
        "control_neutral_pure_tone",
        "control_spectrally_matched_noise",
    ]
    if include_familiar_command:
        controls.append("control_familiar_human_verbal_command")

    # Aim for roughly 40-50% target cues and 50-60% controls in balanced pairs
    schedule: list[str] = []
    n_target = max(2, total_trials // 2)
    n_ctrl = total_trials - n_target

    pool = ["target_engine_b_cue"] * n_target
    ctrl_pool = []
    while len(ctrl_pool) < n_ctrl:
        sub = list(controls)
        rng.shuffle(sub)
        ctrl_pool.extend(sub)
    pool.extend(ctrl_pool[:n_ctrl])
    rng.shuffle(pool)

    # Prevent >2 consecutive identical conditions
    cleaned: list[str] = []
    for cond in pool:
        if len(cleaned) >= 2 and cleaned[-1] == cond and cleaned[-2] == cond:
            # Swap with later item
            alt = [c for c in pool if c != cond]
            if alt:
                cond = rng.choice(alt)
        cleaned.append(cond)

    return cleaned[:total_trials]


def synthesize_control_audio(
    condition: str,
    sr: int = 22050,
    duration_sec: float = 1.5,
    reference_f0: float = 350.0,
    formants: list[float] | None = None,
) -> np.ndarray:
    """
    Synthesize mathematically controlled acoustic waveforms for C1, C2, and C3.
    """
    n_samples = max(16, int(sr * duration_sec))
    t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

    if condition == "control_silent_baseline":
        return np.zeros(n_samples, dtype=np.float32)

    elif condition == "control_neutral_pure_tone":
        # Pure sinusoidal 500 Hz tone with 50 ms cosine-squared onset/offset ramps
        tone_freq = 500.0
        sig = 0.5 * np.sin(2 * np.pi * tone_freq * t)
        ramp_len = min(n_samples // 4, int(sr * 0.05))
        if ramp_len > 0:
            ramp_up = np.sin(0.5 * np.pi * np.linspace(0, 1, ramp_len)) ** 2
            ramp_down = np.cos(0.5 * np.pi * np.linspace(0, 1, ramp_len)) ** 2
            sig[:ramp_len] *= ramp_up
            sig[-ramp_len:] *= ramp_down
        return sig.astype(np.float32)

    elif condition == "control_spectrally_matched_noise":
        # Pink noise filtered through the same formant resonators as Engine B,
        # lacking glottal harmonic periodicity (F0)
        rng = np.random.default_rng(12345)
        white = rng.normal(0.0, 0.4, size=n_samples).astype(np.float32)
        # 1-pole filter to generate pink spectral roll-off
        b0, a1 = 0.05, 0.95
        pink = np.zeros_like(white)
        accum = 0.0
        for i in range(n_samples):
            accum = b0 * white[i] + a1 * accum
            pink[i] = accum

        fmt_list = formants or [650.0, 1500.0, 2700.0]
        out = pink
        for fmt in fmt_list:
            bw = max(40.0, fmt * 0.12)
            out = _two_pole_resonator(out, fmt, bw, sr)
        peak = float(np.max(np.abs(out))) or 1.0
        return (out / peak * 0.5).astype(np.float32)

    return np.zeros(n_samples, dtype=np.float32)


def compute_inter_reviewer_agreement(
    trials: list[models.BehaviouralTrial],
    reviews: list[models.TrialIndependentReview],
) -> dict[str, Any]:
    """Compute observed agreement and Cohen's kappa across independent blind reviews."""
    by_id = {t.id: t for t in trials}
    pairs: list[tuple[str, str]] = []
    for rev in reviews:
        t = by_id.get(rev.trial_id)
        if t:
            pairs.append((t.outcome_category, rev.scored_outcome_category))

    n = len(pairs)
    if n == 0:
        return {
            "paired_reviews": 0,
            "observed_agreement": None,
            "cohens_kappa": None,
            "disagreements_count": 0,
            "status": "no_independent_reviews",
        }

    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    pe = sum(
        (sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n)
        for c in cats
    )
    kappa = 1.0 if abs(1.0 - pe) < 1e-12 else (po - pe) / (1.0 - pe)
    return {
        "paired_reviews": n,
        "observed_agreement": round(po, 4),
        "cohens_kappa": round(float(max(-1.0, min(1.0, kappa))), 4),
        "disagreements_count": n - agree,
        "status": "calculated",
    }


def compute_experimental_metrics(
    trials: list[models.BehaviouralTrial],
    reviews: list[models.TrialIndependentReview] | None = None,
    adverse_events_count: int = 0,
) -> dict[str, Any]:
    """
    Compute rigorous repeated-measures behavioral validation metrics across trials.
    Accounts for individual dog clusters, control discrimination, habituation, and welfare.
    """
    agreement = compute_inter_reviewer_agreement(trials, reviews or [])
    total_count = len(trials)
    if total_count == 0:
        empty_controls = {
            cond: {
                "total_presentations": 0,
                "target_action_performed": 0,
                "false_positive_action_rate": 0.0,
                "orienting_rate": 0.0,
            }
            for cond in EXPERIMENTAL_CONDITIONS[1:]
        }
        empty_lat = {"count": 0, "median_ms": None, "q25_ms": None, "q75_ms": None, "mean_ms": None}
        return {
            "status": "insufficient_data",
            "total_trials": 0,
            "valid_trials": 0,
            "message": "No empirical behavioural trials have been logged yet.",
            "sample_size_assessment": {
                "total_trials_recorded": 0,
                "valid_evaluated_trials": 0,
                "excluded_confounded_trials": 0,
                "exclusion_rate": 0.0,
                "distinct_participants_evaluated": 0,
                "pilot_minimum_met": False,
            },
            "target_cue_metrics": {
                "target_presentations": 0,
                "correct_action_rate": 0.0,
                "attention_only_rate": 0.0,
                "incorrect_action_rate": 0.0,
                "no_response_rate": 0.0,
                "latency_to_orient": dict(empty_lat),
                "latency_to_action": dict(empty_lat),
            },
            "discrimination_and_controls": {
                "acoustic_discrimination_ratio": 0.0,
                "target_response_rate": 0.0,
                "control_response_rate": 0.0,
                "control_breakdown": empty_controls,
            },
            "learning_and_habituation": {
                "session_learning_trajectory": [],
                "mean_habituation_index": None,
                "habituation_interpretation": "No empirical behavioural trials have been logged yet.",
            },
            "inter_reviewer_agreement": agreement,
            "animal_welfare_and_safety": {
                "volume_cap_strictly_enforced": True,
                "max_volume_cap_dba": MAX_PLAYBACK_SPL_DBA,
                "welfare_aborts_count": 0,
                "welfare_abort_rate": 0.0,
                "freezing_episodes_count": 0,
                "freezing_rate": 0.0,
                "adverse_events_count": adverse_events_count,
                "safety_assessment": "No trials recorded yet. 75.0 dBA SPL welfare hard cap active.",
            },
        }

    valid_trials = [t for t in trials if t.is_valid and t.outcome_category != "invalid_or_confounded"]
    valid_count = len(valid_trials)
    excluded_count = total_count - valid_count
    exclusion_rate = round(excluded_count / total_count, 4)

    target_trials = [t for t in valid_trials if t.experimental_condition == "target_engine_b_cue"]
    control_trials = [t for t in valid_trials if t.experimental_condition != "target_engine_b_cue"]

    # Counts by outcome category on target cues
    outcome_counts: dict[str, int] = {cat: 0 for cat in OUTCOME_CATEGORIES}
    for t in valid_trials:
        if t.outcome_category in outcome_counts:
            outcome_counts[t.outcome_category] += 1

    target_valid_count = len(target_trials)
    target_correct = sum(1 for t in target_trials if t.outcome_category == "correct_target_action")
    target_attention_only = sum(1 for t in target_trials if t.outcome_category == "attention_only")
    target_incorrect = sum(1 for t in target_trials if t.outcome_category == "incorrect_action")
    target_no_response = sum(1 for t in target_trials if t.outcome_category == "no_observable_response")

    correct_action_rate = round(target_correct / max(1, target_valid_count), 4) if target_valid_count else 0.0
    attention_only_rate = round(target_attention_only / max(1, target_valid_count), 4) if target_valid_count else 0.0
    incorrect_action_rate = round(target_incorrect / max(1, target_valid_count), 4) if target_valid_count else 0.0
    no_response_rate = round(target_no_response / max(1, target_valid_count), 4) if target_valid_count else 0.0

    # Control condition response rates
    control_breakdown: dict[str, dict[str, Any]] = {}
    ctrl_any_response_count = 0
    for cond in EXPERIMENTAL_CONDITIONS[1:]:
        c_subset = [t for t in control_trials if t.experimental_condition == cond]
        c_count = len(c_subset)
        c_target_act = sum(1 for t in c_subset if t.outcome_category == "correct_target_action")
        c_orient = sum(1 for t in c_subset if t.outcome_category in {"correct_target_action", "attention_only"})
        ctrl_any_response_count += c_orient
        control_breakdown[cond] = {
            "total_presentations": c_count,
            "target_action_performed": c_target_act,
            "false_positive_action_rate": round(c_target_act / max(1, c_count), 4) if c_count else 0.0,
            "orienting_rate": round(c_orient / max(1, c_count), 4) if c_count else 0.0,
        }

    # Acoustic Discrimination Ratio
    # D_ratio = (R_target - R_control) / max(1e-5, R_target + R_control)
    r_target_resp = (target_correct + target_attention_only) / max(1, target_valid_count) if target_valid_count else 0.0
    r_ctrl_resp = ctrl_any_response_count / max(1, len(control_trials)) if control_trials else 0.0
    denom = max(1e-5, r_target_resp + r_ctrl_resp)
    discrimination_ratio = round((r_target_resp - r_ctrl_resp) / denom, 4)

    # Response Latency Distribution on Target Cues
    orient_latencies = [t.latency_to_orient_ms for t in target_trials if t.latency_to_orient_ms is not None]
    action_latencies = [t.latency_to_action_ms for t in target_trials if t.latency_to_action_ms is not None]

    def _latency_stats(vals: list[float]) -> dict[str, Any]:
        if not vals:
            return {"count": 0, "median_ms": None, "q25_ms": None, "q75_ms": None, "mean_ms": None}
        arr = np.sort(vals)
        return {
            "count": len(arr),
            "median_ms": round(float(np.median(arr)), 1),
            "q25_ms": round(float(np.percentile(arr, 25)), 1),
            "q75_ms": round(float(np.percentile(arr, 75)), 1),
            "mean_ms": round(float(np.mean(arr)), 1),
        }

    orient_stats = _latency_stats(orient_latencies)
    action_stats = _latency_stats(action_latencies)

    # Learning Curve: Session-by-Session Correct Action Trajectory
    sessions: dict[str, list[models.BehaviouralTrial]] = {}
    for t in valid_trials:
        sessions.setdefault(t.session_id, []).append(t)

    session_trajectory = []
    for s_id, s_trials in sorted(sessions.items(), key=lambda kv: kv[1][0].playback_timestamp):
        s_target = [t for t in s_trials if t.experimental_condition == "target_engine_b_cue"]
        s_corr = sum(1 for t in s_target if t.outcome_category == "correct_target_action")
        s_rate = round(s_corr / max(1, len(s_target)), 4) if s_target else 0.0
        session_trajectory.append({
            "session_id": s_id,
            "target_trials": len(s_target),
            "correct_actions": s_corr,
            "correct_action_rate": s_rate,
            "date": s_trials[0].playback_timestamp.isoformat(),
        })

    # Habituation Index: comparing first half vs second half latencies in sessions with >= 6 trials
    habituation_indices = []
    for s_trials in sessions.values():
        s_target = [t for t in s_trials if t.experimental_condition == "target_engine_b_cue" and t.latency_to_orient_ms]
        if len(s_target) >= 4:
            mid = len(s_target) // 2
            early_lat = np.mean([t.latency_to_orient_ms for t in s_target[:mid]])
            late_lat = np.mean([t.latency_to_orient_ms for t in s_target[mid:]])
            if early_lat > 0:
                h_idx = max(-1.0, min(1.0, 1.0 - (late_lat / early_lat)))
                habituation_indices.append(h_idx)
    mean_habituation_index = round(float(np.mean(habituation_indices)), 4) if habituation_indices else None

    # Welfare Metrics
    abort_count = sum(1 for t in trials if t.abort_triggered or t.outcome_category == "welfare_terminated")
    freezing_count = sum(1 for t in trials if t.freezing_observed)
    welfare_abort_rate = round(abort_count / max(1, total_count), 4)
    freezing_rate = round(freezing_count / max(1, total_count), 4)

    # Participant breakdown
    participants = {t.participant_id for t in trials}
    participant_count = len(participants)

    return {
        "status": "pilot_data_collected" if valid_count >= 10 else "insufficient_sample_size",
        "sample_size_assessment": {
            "total_trials_recorded": total_count,
            "valid_evaluated_trials": valid_count,
            "excluded_confounded_trials": excluded_count,
            "exclusion_rate": exclusion_rate,
            "distinct_participants_evaluated": participant_count,
            "pilot_minimum_met": valid_count >= 30,
        },
        "target_cue_metrics": {
            "target_presentations": target_valid_count,
            "correct_action_rate": correct_action_rate,
            "attention_only_rate": attention_only_rate,
            "incorrect_action_rate": incorrect_action_rate,
            "no_response_rate": no_response_rate,
            "latency_to_orient": orient_stats,
            "latency_to_action": action_stats,
        },
        "discrimination_and_controls": {
            "acoustic_discrimination_ratio": discrimination_ratio,
            "target_response_rate": round(r_target_resp, 4),
            "control_response_rate": round(r_ctrl_resp, 4),
            "control_breakdown": control_breakdown,
        },
        "learning_and_habituation": {
            "session_learning_trajectory": session_trajectory,
            "mean_habituation_index": mean_habituation_index,
            "habituation_interpretation": (
                "Moderate sensory habituation detected across trial blocks; variable reinforcement advised."
                if (mean_habituation_index and mean_habituation_index > 0.4)
                else "Response latency remained stable across trial repetitions."
            ),
        },
        "inter_reviewer_agreement": agreement,
        "animal_welfare_and_safety": {
            "volume_cap_strictly_enforced": True,
            "max_volume_cap_dba": MAX_PLAYBACK_SPL_DBA,
            "welfare_aborts_count": abort_count,
            "welfare_abort_rate": welfare_abort_rate,
            "freezing_episodes_count": freezing_count,
            "freezing_rate": freezing_rate,
            "adverse_events_count": adverse_events_count,
            "safety_assessment": (
                "PASS: Welfare aborts and freezing rates within safe boundaries (<5%)."
                if welfare_abort_rate < 0.05 and freezing_rate < 0.05
                else "CAUTION: Elevated distress or freezing observed; protocol volume and stress screening require review."
            ),
        },
    }


def export_pseudonymous_research_archive(
    db: Session,
    user: models.User,
    format_type: str = "json",
) -> tuple[str, str]:
    """
    Export anonymized/pseudonymous empirical trial records without exposing
    private owner names, emails, internal file paths, or credentials.
    """
    stmt = (
        select(models.BehaviouralTrial)
        .where(models.BehaviouralTrial.user_id == user.id)
        .order_by(models.BehaviouralTrial.created_at.asc())
    )
    trials = list(db.scalars(stmt))

    # Participant lookup (pseudonyms only)
    participants = {p.id: p for p in db.scalars(select(models.StudyParticipant).where(models.StudyParticipant.user_id == user.id))}
    cues = {c.id: c for c in db.scalars(select(models.ExperimentalCue).where(models.ExperimentalCue.user_id == user.id))}

    clean_records = []
    for t in trials:
        part = participants.get(t.participant_id)
        cue = cues.get(t.cue_id) if t.cue_id else None

        clean_records.append({
            "trial_id": t.id,
            "participant_pseudonym": part.pseudonym if part else "UNKNOWN-PARTICIPANT",
            "participant_breed": part.breed if part else "unknown",
            "participant_sex": part.sex if part else "unknown",
            "participant_age_years": part.age_years if part else None,
            "session_id": t.session_id,
            "trial_order": t.trial_order_in_session,
            "experimental_condition": t.experimental_condition,
            "cue_label": cue.cue_label if cue else None,
            "target_intention": cue.target_intention if cue else None,
            "action_category": cue.action_category if cue else None,
            "cue_f0_hz": cue.f0_hz if cue else None,
            "pre_cue_state": t.pre_cue_state,
            "measured_spl_dba": t.measured_spl_dba,
            "handler_behaviour": t.handler_behaviour,
            "first_response": t.first_response,
            "latency_to_orient_ms": t.latency_to_orient_ms,
            "latency_to_action_ms": t.latency_to_action_ms,
            "outcome_category": t.outcome_category,
            "reinforcement_provided": t.reinforcement_provided,
            "environmental_distractions": t.environmental_distractions,
            "freezing_observed": t.freezing_observed,
            "abort_triggered": t.abort_triggered,
            "is_valid": t.is_valid,
            "exclusion_reason": t.exclusion_reason,
            "created_at_utc": t.created_at.isoformat(),
        })

    if format_type == "csv":
        if not clean_records:
            return "trial_id,participant_pseudonym,outcome_category\n", "text/csv"
        buf = io.StringIO()
        fieldnames = list(clean_records[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_records)
        return buf.getvalue(), "text/csv"

    # Default JSON
    trial_ids = [t.id for t in trials]
    reviews = (
        list(db.scalars(select(models.TrialIndependentReview).where(models.TrialIndependentReview.trial_id.in_(trial_ids))))
        if trial_ids
        else []
    )
    adverse_count = len(list(db.scalars(select(models.TrialAdverseEvent).where(models.TrialAdverseEvent.user_id == user.id))))
    metrics = compute_experimental_metrics(trials, reviews=reviews, adverse_events_count=adverse_count)
    archive = {
        "metadata": {
            "archive_version": "2.0.0-csai-research",
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_version": PROTOCOL_VERSION,
            "total_trials": len(clean_records),
            "privacy_notice": "Contains pseudonymous canine behavioral telemetry only. All owner personal information scrubbed.",
        },
        "aggregate_metrics": metrics,
        "trials": clean_records,
    }
    return json.dumps(archive, indent=2), "application/json"
