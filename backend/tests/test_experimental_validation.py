"""
Priority 7 — Real-World Canine Communication & Experimental Validation Test Suite.
Verifies participant consent, cue reproducibility, 75 dBA volume caps, Latin square schedules,
trial logging, independent blind video review, scientific metrics, and tenant isolation.
"""

from __future__ import annotations

import io
import json
import pytest
from fastapi.testclient import TestClient

from app import models
from tests.conftest import auth_header


def test_participant_registration_and_consent_enforcement(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    # 1. Missing owner consent must fail with 400
    res_no_consent = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={
            "pseudonym": "DOG-PILOT-01",
            "owner_consent_confirmed": False,
            "welfare_review_confirmed": True,
        },
    )
    assert res_no_consent.status_code == 400
    assert "consent" in res_no_consent.text.lower()

    # 2. Missing welfare review must fail with 400
    res_no_welfare = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={
            "pseudonym": "DOG-PILOT-01",
            "owner_consent_confirmed": True,
            "welfare_review_confirmed": False,
        },
    )
    assert res_no_welfare.status_code == 400
    assert "welfare" in res_no_welfare.text.lower()

    # 3. Valid registration succeeds with pseudonymous profile
    res_valid = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={
            "pseudonym": "DOG-PILOT-01",
            "owner_consent_confirmed": True,
            "welfare_review_confirmed": True,
            "breed": "Border Collie",
            "sex": "female",
            "age_years": 3.5,
            "familiarity_with_target_action": "emerging",
            "training_history_notes": "Basic positive reinforcement obedience.",
        },
    )
    assert res_valid.status_code == 201
    p_data = res_valid.json()
    assert p_data["pseudonym"] == "DOG-PILOT-01"
    assert p_data["owner_consent_confirmed"] is True
    assert p_data["welfare_review_confirmed"] is True

    # 4. Listing participants returns the registered study participant
    res_list = client.get("/api/experiments/participants", headers=hdr)
    assert res_list.status_code == 200
    items = res_list.json()
    assert any(i["id"] == p_data["id"] for i in items)


def test_experimental_cue_registration_and_75dba_cap(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    # 1. Cue exceeding 75.0 dBA SPL must be rejected by veterinary safety hard cap
    res_over_vol = client.post(
        "/api/experiments/cues",
        headers=hdr,
        json={
            "cue_label": "High Volume Recall",
            "target_intention": "come",
            "target_action_description": "Dog approaches handler within 2.5s",
            "action_category": "learned_action",
            "peak_spl_dba": 78.5,  # Exceeds 75.0 dBA
            "f0_hz": 420.0,
        },
    )
    assert res_over_vol.status_code == 422
    assert "75" in res_over_vol.text

    # 2. Cue within safe volume cap (65 dBA) succeeds and computes audio SHA256
    res_valid = client.post(
        "/api/experiments/cues",
        headers=hdr,
        json={
            "cue_label": "Standard Recall Cue v1",
            "target_intention": "come",
            "target_action_description": "Dog executes forward approach to handler within 2.5s",
            "action_category": "learned_action",
            "peak_spl_dba": 65.0,
            "f0_hz": 420.0,
            "synthesis_method": "method_d_parametric_glottal",
            "synthesis_params": {
                "f0": 420.0,
                "formants": [620.0, 1450.0, 2600.0],
                "subharmonic_mix": 0.2,
            },
        },
    )
    assert res_valid.status_code == 201
    c_data = res_valid.json()
    assert c_data["target_intention"] == "come"
    assert c_data["action_category"] == "learned_action"
    assert len(c_data["sha256"]) == 64
    assert c_data["cue_version"] == 1


def test_randomized_counterbalanced_schedule(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    # Register participant and cue
    p_res = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": "DOG-SCHED-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    )
    c_res = client.post(
        "/api/experiments/cues",
        headers=hdr,
        json={
            "cue_label": "Attention Chirp",
            "target_intention": "attention",
            "target_action_description": "Orienting head turn to speaker",
            "action_category": "attention",
            "peak_spl_dba": 60.0,
            "f0_hz": 520.0,
        },
    )
    p_id = p_res.json()["id"]
    c_id = c_res.json()["id"]

    # Generate schedule with fixed seed 424242
    s1 = client.post(
        "/api/experiments/schedules",
        headers=hdr,
        json={"participant_id": p_id, "cue_id": c_id, "session_number": 1, "randomization_seed": 424242, "total_trials": 10},
    ).json()

    # Identical seed reproduces identical schedule sequence
    s2 = client.post(
        "/api/experiments/schedules",
        headers=hdr,
        json={"participant_id": p_id, "cue_id": c_id, "session_number": 1, "randomization_seed": 424242, "total_trials": 10},
    ).json()
    assert s1["planned_conditions"] == s2["planned_conditions"]

    # Schedule contains target cue and control conditions
    conditions = set(s1["planned_conditions"])
    assert "target_engine_b_cue" in conditions
    assert any(c.startswith("control_") for c in conditions)


def test_trial_logging_volume_cap_and_welfare_abort(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    p_id = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": "DOG-TRIAL-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    # 1. Trial exceeding 75 dBA must be rejected
    r_over = client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-01",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 79.0,  # Exceeds 75 dBA
            "outcome_category": "correct_target_action",
        },
    )
    assert r_over.status_code == 422
    assert "75" in r_over.text

    # 2. Trial with freezing observed must surface welfare warning
    r_freeze = client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-01",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 64.0,
            "latency_to_orient_ms": 320.0,
            "latency_to_action_ms": 1200.0,
            "outcome_category": "correct_target_action",
            "freezing_observed": True,
        },
    )
    assert r_freeze.status_code == 201
    assert "Freezing/quiescence detected" in r_freeze.json()["welfare_warning"]

    # 3. Trial with abort triggered automatically maps outcome to 'welfare_terminated'
    r_abort = client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-01",
            "trial_order_in_session": 2,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 62.0,
            "outcome_category": "attention_only",
            "abort_triggered": True,
            "abort_reason": "Repeated whale-eye and trembling observed.",
        },
    )
    assert r_abort.status_code == 201
    assert r_abort.json()["outcome_category"] == "welfare_terminated"


def test_independent_blind_review_and_agreement(client: TestClient, user_a: dict, user_b: dict):
    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    p_id = client.post(
        "/api/experiments/participants",
        headers=hdr_a,
        json={"pseudonym": "DOG-REVIEW-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    t_id = client.post(
        "/api/experiments/trials",
        headers=hdr_a,
        json={
            "participant_id": p_id,
            "session_id": "sess-rev-01",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 65.0,
            "outcome_category": "correct_target_action",
        },
    ).json()["id"]

    # Uninvited secondary reviewer (user_b) must be blocked (403)
    rev_uninvited = client.post(
        f"/api/experiments/trials/{t_id}/reviews",
        headers=hdr_b,
        json={
            "reviewer_name": "Dr. Ethologist",
            "is_blind_to_condition": True,
            "scored_outcome_category": "correct_target_action",
        },
    )
    assert rev_uninvited.status_code == 403

    # Owner cannot invite themselves
    inv_self = client.post(
        f"/api/experiments/trials/{t_id}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_a["email"], "permission_scope": "blind_video_review", "is_blind": True},
    )
    assert inv_self.status_code == 400

    # Owner invites user_b explicitly for blind video review
    inv_res = client.post(
        f"/api/experiments/trials/{t_id}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_b["email"], "permission_scope": "blind_video_review", "is_blind": True},
    )
    assert inv_res.status_code == 201, inv_res.text
    inv_id = inv_res.json()["id"]

    # user_b accepts the invitation
    acc_res = client.post(
        f"/api/experiments/invitations/{inv_id}/respond",
        headers=hdr_b,
        json={"decision": "accept"},
    )
    assert acc_res.status_code == 200, acc_res.text
    assert acc_res.json()["status"] == "accepted"

    # Assigned trials for user_b must omit condition and primary outcome (blind protection)
    assigned = client.get("/api/experiments/assigned-trials", headers=hdr_b).json()
    assert len(assigned) == 1
    assert assigned[0]["trial_id"] == t_id
    assert "experimental_condition" not in assigned[0]
    assert "primary_outcome_category" not in assigned[0]

    # Secondary reviewer (user_b) submits blind video scoring
    rev1 = client.post(
        f"/api/experiments/trials/{t_id}/reviews",
        headers=hdr_b,
        json={
            "reviewer_name": "Dr. Ethologist",
            "is_blind_to_condition": True,
            "scored_outcome_category": "correct_target_action",
            "reviewer_confidence": 0.95,
            "review_notes": "Clear forward approach to target within 2s.",
        },
    )
    assert rev1.status_code == 201
    assert "primary_observer_category" not in rev1.json()
    assert "disagreement_with_primary" not in rev1.json()

    # Study owner inspects reviews and inter-reviewer agreement
    owner_revs = client.get(f"/api/experiments/trials/{t_id}/reviews", headers=hdr_a)
    assert owner_revs.status_code == 200
    assert owner_revs.json()[0]["disagreement_with_primary"] is False

    # Same reviewer cannot submit duplicate review
    rev_dup = client.post(
        f"/api/experiments/trials/{t_id}/reviews",
        headers=hdr_b,
        json={
            "reviewer_name": "Dr. Ethologist",
            "scored_outcome_category": "attention_only",
        },
    )
    assert rev_dup.status_code == 409

    # Owner revokes invitation; assigned-trials no longer exposes the trial
    revk = client.post(f"/api/experiments/invitations/{inv_id}/revoke", headers=hdr_a)
    assert revk.status_code == 200
    assert client.get("/api/experiments/assigned-trials", headers=hdr_b).json() == []


def test_auditable_trial_correction(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    p_id = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": "DOG-AUDIT-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    t_id = client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-corr-01",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 63.0,
            "outcome_category": "attention_only",
        },
    ).json()["id"]

    # Apply correction with audit note
    patch_res = client.patch(
        f"/api/experiments/trials/{t_id}",
        headers=hdr,
        json={
            "outcome_category": "correct_target_action",
            "correction_note": "Video replay at 0.5x speed shows dog initiated full retrieve action before 2.0s.",
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["outcome_category"] == "correct_target_action"
    assert patch_res.json()["correction_count"] == 1


def test_scientific_metrics_and_discrimination_ratio(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    p_id = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": "DOG-METRIC-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    # Log 3 target cue trials: 2 correct, 1 attention only
    for i in range(2):
        client.post(
            "/api/experiments/trials",
            headers=hdr,
            json={
                "participant_id": p_id,
                "session_id": "sess-met-01",
                "trial_order_in_session": i + 1,
                "experimental_condition": "target_engine_b_cue",
                "measured_spl_dba": 65.0,
                "latency_to_orient_ms": 250.0 + i * 20.0,
                "latency_to_action_ms": 1100.0 + i * 50.0,
                "outcome_category": "correct_target_action",
            },
        )
    client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-met-01",
            "trial_order_in_session": 3,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 65.0,
            "latency_to_orient_ms": 400.0,
            "outcome_category": "attention_only",
        },
    )

    # Log 2 control trials: 1 neutral pure tone (no response), 1 silent baseline (no response)
    client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-met-01",
            "trial_order_in_session": 4,
            "experimental_condition": "control_neutral_pure_tone",
            "measured_spl_dba": 65.0,
            "outcome_category": "no_observable_response",
        },
    )
    client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p_id,
            "session_id": "sess-met-01",
            "trial_order_in_session": 5,
            "experimental_condition": "control_silent_baseline",
            "measured_spl_dba": 35.0,
            "outcome_category": "no_observable_response",
        },
    )

    # Compute metrics
    m_res = client.get("/api/experiments/metrics", headers=hdr)
    assert m_res.status_code == 200
    metrics = m_res.json()

    assert metrics["sample_size_assessment"]["valid_evaluated_trials"] == 5
    assert metrics["target_cue_metrics"]["target_presentations"] == 3
    assert metrics["target_cue_metrics"]["correct_action_rate"] == round(2 / 3, 4)
    assert metrics["target_cue_metrics"]["attention_only_rate"] == round(1 / 3, 4)
    assert metrics["target_cue_metrics"]["latency_to_orient"]["median_ms"] is not None

    # Discrimination ratio: response on target (100%) vs response on control (0%) -> D_ratio == 1.0
    assert metrics["discrimination_and_controls"]["acoustic_discrimination_ratio"] == 1.0


def test_pseudonymous_research_export(client: TestClient, user_a: dict):
    hdr = auth_header(user_a["token"])

    # JSON export
    res_json = client.get("/api/experiments/export?format=json", headers=hdr)
    assert res_json.status_code == 200
    assert res_json.headers["content-type"] == "application/json"
    data = res_json.json()
    assert "metadata" in data
    assert "trials" in data
    # Verify no private emails or passwords leaked
    raw_str = json.dumps(data)
    assert user_a["email"] not in raw_str
    assert "password" not in raw_str.lower()

    # CSV export
    res_csv = client.get("/api/experiments/export?format=csv", headers=hdr)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "participant_pseudonym" in res_csv.text


def test_tenant_isolation_on_participants_and_trials(client: TestClient, user_a: dict, user_b: dict):
    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    # User A registers participant
    p_a = client.post(
        "/api/experiments/participants",
        headers=hdr_a,
        json={"pseudonym": "DOG-USER-A", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    # User B cannot see User A's participant in their list
    list_b = client.get("/api/experiments/participants", headers=hdr_b).json()
    assert all(p["id"] != p_a for p in list_b)

    # User B cannot log a trial referencing User A's participant
    trial_b = client.post(
        "/api/experiments/trials",
        headers=hdr_b,
        json={
            "participant_id": p_a,
            "session_id": "sess-b-illegal",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 65.0,
            "outcome_category": "correct_target_action",
        },
    )
    assert trial_b.status_code == 404


def test_schedule_without_seed_and_cross_tenant_fk_isolation(client: TestClient, user_a: dict, user_b: dict):
    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    p_a = client.post(
        "/api/experiments/participants",
        headers=hdr_a,
        json={"pseudonym": "DOG-SEED-A", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]
    c_a = client.post(
        "/api/experiments/cues",
        headers=hdr_a,
        json={
            "cue_label": "Seedless Cue",
            "target_intention": "come",
            "target_action_description": "Approach handler within 3 seconds",
            "action_category": "learned_action",
            "peak_spl_dba": 64.0,
            "f0_hz": 380.0,
        },
    ).json()["id"]

    # Omitting randomization_seed must auto-generate a seed without NameError
    sched_res = client.post(
        "/api/experiments/schedules",
        headers=hdr_a,
        json={"participant_id": p_a, "cue_id": c_a, "session_number": 1, "total_trials": 8},
    )
    assert sched_res.status_code == 201, sched_res.text
    assert 100000 <= sched_res.json()["randomization_seed"] < 1000000

    # User B cannot link User A's cue_id into User B's trial
    p_b = client.post(
        "/api/experiments/participants",
        headers=hdr_b,
        json={"pseudonym": "DOG-SEED-B", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]
    bad_trial = client.post(
        "/api/experiments/trials",
        headers=hdr_b,
        json={
            "participant_id": p_b,
            "cue_id": c_a,
            "session_id": "sess-b-fk",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 62.0,
            "outcome_category": "attention_only",
        },
    )
    assert bad_trial.status_code == 404


def test_empty_experimental_metrics_schema_complete(client: TestClient, user_a: dict):
    hdr_a = auth_header(user_a["token"])
    res = client.get("/api/experiments/metrics", headers=hdr_a)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "insufficient_data"
    assert body["total_trials"] == 0
    assert body["target_cue_metrics"]["correct_action_rate"] == 0.0
    assert body["discrimination_and_controls"]["acoustic_discrimination_ratio"] == 0.0
    assert body["animal_welfare_and_safety"]["max_volume_cap_dba"] == 75.0


def test_reviewer_invitation_revocation_expiration_and_preregistration(client: TestClient, user_a: dict, user_b: dict):
    from datetime import datetime, timedelta, timezone
    from app.db import SessionLocal

    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    # Preregistration & Adverse Events
    pre = client.post(
        "/api/experiments/preregistrations",
        headers=hdr_a,
        json={
            "study_title": "Pilot Recall Conditioning Protocol v1",
            "hypothesis": "Conditioned canine-prosody cues yield higher target recall than C1-C3 controls after 10 conditioning sessions.",
            "target_behaviour": "Approach handler within 2.5s without visual gesture.",
            "baseline_measurement_plan": "3-minute resting baseline prior to trial block.",
        },
    )
    assert pre.status_code == 201, pre.text
    assert len(client.get("/api/experiments/preregistrations", headers=hdr_a).json()) == 1

    p_id = client.post(
        "/api/experiments/participants",
        headers=hdr_a,
        json={"pseudonym": "DOG-PREREG-01", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    ).json()["id"]

    t1 = client.post(
        "/api/experiments/trials",
        headers=hdr_a,
        json={
            "participant_id": p_id,
            "session_id": "sess-sec-01",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 64.0,
            "outcome_category": "attention_only",
        },
    ).json()["id"]

    ae = client.post(
        "/api/experiments/adverse-events",
        headers=hdr_a,
        json={
            "participant_id": p_id,
            "trial_id": t1,
            "severity": "mild",
            "distress_indicators": ["lip_licking"],
            "action_taken": "Paused session for 5 minutes and offered water.",
            "session_aborted": False,
        },
    )
    assert ae.status_code == 201, ae.text

    # Owner cannot review own trial
    self_rev = client.post(
        f"/api/experiments/trials/{t1}/reviews",
        headers=hdr_a,
        json={"reviewer_name": "Owner", "scored_outcome_category": "attention_only"},
    )
    assert self_rev.status_code == 403

    # Inviting then revoking BEFORE review blocks submission
    inv1 = client.post(
        f"/api/experiments/trials/{t1}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_b["email"], "is_blind": True},
    ).json()["id"]
    assert client.post(f"/api/experiments/invitations/{inv1}/respond", headers=hdr_b, json={"decision": "accept"}).status_code == 200
    assert client.post(f"/api/experiments/invitations/{inv1}/revoke", headers=hdr_a).status_code == 200
    after_revoke = client.post(
        f"/api/experiments/trials/{t1}/reviews",
        headers=hdr_b,
        json={"reviewer_name": "Dr. B", "scored_outcome_category": "attention_only"},
    )
    assert after_revoke.status_code == 403

    # Expired invitation is blocked
    inv2 = client.post(
        f"/api/experiments/trials/{t1}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_b["email"], "is_blind": True, "expires_in_hours": 1},
    ).json()["id"]
    with SessionLocal() as s:
        row = s.get(models.TrialReviewerInvitation, inv2)
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        s.commit()
    exp_resp = client.post(
        f"/api/experiments/invitations/{inv2}/respond",
        headers=hdr_b,
        json={"decision": "accept"},
    )
    assert exp_resp.status_code == 403
