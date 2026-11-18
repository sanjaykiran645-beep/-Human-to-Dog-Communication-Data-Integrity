"""Phase 14 — Comprehensive security closure tests: 7 negative reviewer scenarios, deletion erasure, and abuse checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import config, db, models
from tests.conftest import auth_header, write_bursts


def _create_trial_for(client, hdr: dict[str, str], pseudonym: str = "SEC-DOG-1") -> str:
    p = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": pseudonym, "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    )
    assert p.status_code == 201, p.text
    t = client.post(
        "/api/experiments/trials",
        headers=hdr,
        json={
            "participant_id": p.json()["id"],
            "session_id": f"sess-{pseudonym}",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 63.0,
            "outcome_category": "correct_target_action",
        },
    )
    assert t.status_code == 201, t.text
    return t.json()["id"]


def test_phase14_seven_negative_reviewer_scenarios(client, user_a, user_b):
    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    # Register a third user C for cross-reviewer negative checks
    r_c = client.post(
        "/api/auth/register",
        json={"email": "sec-user-c@example.com", "password": "correcthorse", "name": "Cora"},
    )
    assert r_c.status_code == 200
    hdr_c = auth_header(r_c.json()["access_token"])

    trial_a = _create_trial_for(client, hdr_a, "NEG-DOG-A")

    # 1. User B cannot read User A's trial or reviews
    assert all(tr["id"] != trial_a for tr in client.get("/api/experiments/trials", headers=hdr_b).json())
    assert client.get(f"/api/experiments/trials/{trial_a}/reviews", headers=hdr_b).status_code == 404

    # 2. Unassigned reviewer cannot access trial or submit review
    assert all(tr["trial_id"] != trial_a for tr in client.get("/api/experiments/assigned-trials", headers=hdr_b).json())
    assert (
        client.post(
            f"/api/experiments/trials/{trial_a}/reviews",
            headers=hdr_b,
            json={"reviewer_name": "Uninvited", "scored_outcome_category": "attention_only", "is_blind_to_condition": True},
        ).status_code
        == 403
    )

    # Invite User B (blind)
    inv_b = client.post(
        f"/api/experiments/trials/{trial_a}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_b["email"], "is_blind": True},
    )
    assert inv_b.status_code == 201
    inv_b_id = inv_b.json()["id"]

    # User C cannot respond to User B's invitation
    assert client.post(f"/api/experiments/invitations/{inv_b_id}/respond", headers=hdr_c, json={"decision": "accept"}).status_code == 403

    # User B accepts and submits blinded review
    assert client.post(f"/api/experiments/invitations/{inv_b_id}/respond", headers=hdr_b, json={"decision": "accept"}).status_code == 200

    # 6. Blinded reviewer cannot see condition or primary observer outcome in queue or review response
    assigned = [x for x in client.get("/api/experiments/assigned-trials", headers=hdr_b).json() if x["trial_id"] == trial_a]
    assert len(assigned) == 1
    assert "experimental_condition" not in assigned[0]
    assert "primary_outcome_category" not in assigned[0]

    rev_res = client.post(
        f"/api/experiments/trials/{trial_a}/reviews",
        headers=hdr_b,
        json={"reviewer_name": "Bea", "scored_outcome_category": "correct_target_action", "is_blind_to_condition": False},
    )
    assert rev_res.status_code == 201
    assert rev_res.json()["is_blind_to_condition"] is True
    assert "primary_observer_category" not in rev_res.json()
    assert "disagreement_with_primary" not in rev_res.json()
    assert client.get(f"/api/experiments/trials/{trial_a}/reviews", headers=hdr_b).status_code == 404

    # 5. Reviewer cannot modify trial or resubmit/tamper review
    assert (
        client.patch(
            f"/api/experiments/trials/{trial_a}",
            headers=hdr_b,
            json={"outcome_category": "no_observable_response", "correction_note": "tamper test"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/experiments/trials/{trial_a}/reviews",
            headers=hdr_b,
            json={"reviewer_name": "Bea", "scored_outcome_category": "no_observable_response", "is_blind_to_condition": True},
        ).status_code
        == 409
    )

    # 3. Revoked reviewer cannot submit review (on a new trial where invited then revoked)
    trial_a2 = _create_trial_for(client, hdr_a, "NEG-DOG-A2")
    inv_rev = client.post(
        f"/api/experiments/trials/{trial_a2}/invitations",
        headers=hdr_a,
        json={"reviewer_email": user_b["email"], "is_blind": True},
    ).json()["id"]
    assert client.post(f"/api/experiments/invitations/{inv_rev}/respond", headers=hdr_b, json={"decision": "accept"}).status_code == 200
    assert client.post(f"/api/experiments/invitations/{inv_rev}/revoke", headers=hdr_a).status_code == 200
    assert (
        client.post(
            f"/api/experiments/trials/{trial_a2}/reviews",
            headers=hdr_b,
            json={"reviewer_name": "Bea", "scored_outcome_category": "attention_only", "is_blind_to_condition": True},
        ).status_code
        == 403
    )

    # 4. Expired invitation cannot be accepted
    inv_exp = client.post(
        f"/api/experiments/trials/{trial_a2}/invitations",
        headers=hdr_a,
        json={"reviewer_email": "sec-user-c@example.com", "is_blind": True},
    ).json()["id"]
    with db.SessionLocal() as session:
        row = session.get(models.TrialReviewerInvitation, inv_exp)
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()
    assert client.post(f"/api/experiments/invitations/{inv_exp}/respond", headers=hdr_c, json={"decision": "accept"}).status_code == 403

    # 7. Unauthenticated & cross-tenant private research export isolation
    assert client.get("/api/experiments/export?format=json").status_code == 401
    export_b = client.get("/api/experiments/export?format=json", headers=hdr_b).json()
    assert export_b["trials"] == []

    # Clean up extra user C
    assert client.delete("/api/account", headers=hdr_c).status_code == 200


def test_phase14_account_deletion_erasure_token_revocation_and_upload_safety(client, user_a, tmp_path: Path):
    hdr = auth_header(user_a["token"])
    uid = user_a["user"]["id"]

    # Create full cross-table footprint: dog, recording, preregistration, participant, trial, adverse event
    dog_id = client.post("/api/dogs", headers=hdr, json={"name": "'; DROP TABLE users;--", "breed": "Beagle"}).json()["id"]
    wav = write_bursts(tmp_path / "erase.wav")
    with wav.open("rb") as fh:
        assert client.post("/api/recordings/analyze", headers=hdr, data={"dog_id": dog_id}, files={"file": ("../../etc/passwd.wav", fh, "audio/wav")}).status_code == 200
    pre = client.post(
        "/api/experiments/preregistrations",
        headers=hdr,
        json={
            "study_title": "Erase Check",
            "hypothesis": "Test full cascade",
            "target_behaviour": "attention_only",
            "success_criteria": {"alpha": 0.05},
            "baseline_measurement_plan": "30s silence",
            "randomization_rule": "latin-square",
            "termination_rules": "stop on freeze",
            "missing_data_policy": "exclude invalid",
            "statistical_analysis_plan": "exact binomial",
        },
    )
    assert pre.status_code == 201
    part = client.post(
        "/api/experiments/participants",
        headers=hdr,
        json={"pseudonym": "ERASE-01", "dog_id": dog_id, "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    )
    assert part.status_code == 201
    tr_id = _create_trial_for(client, hdr, "ERASE-02")
    ae = client.post(
        "/api/experiments/adverse-events",
        headers=hdr,
        json={"participant_id": part.json()["id"], "trial_id": tr_id, "severity": "mild", "action_taken": "paused"},
    )
    assert ae.status_code == 201

    # Executable / HTML upload disguised as WAV rejected
    bad_wav = tmp_path / "spoof.wav"
    bad_wav.write_bytes(b"<!doctype html><script>alert(1)</script>")
    with bad_wav.open("rb") as fh:
        spoof = client.post("/api/recordings/analyze", headers=hdr, files={"file": ("spoof.wav", fh, "audio/wav")})
    assert spoof.status_code == 400

    # Delete account revokes active token and erases every owned DB record and file
    assert client.delete("/api/account", headers=hdr).status_code == 200
    assert client.get("/api/auth/me", headers=hdr).status_code == 401
    assert not (config.STORAGE_DIR / uid).exists()
    with db.SessionLocal() as session:
        assert session.get(models.User, uid) is None
        assert session.query(models.Dog).filter(models.Dog.user_id == uid).count() == 0
        assert session.query(models.Recording).filter(models.Recording.user_id == uid).count() == 0
        assert session.query(models.TrialPreregistration).filter(models.TrialPreregistration.user_id == uid).count() == 0
        assert session.query(models.TrialAdverseEvent).filter(models.TrialAdverseEvent.user_id == uid).count() == 0
        assert session.query(models.AuditEvent).filter(models.AuditEvent.user_id == uid).count() == 0
