import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}




@pytest.fixture
def auth_user(client):
    email = f"annotator-{os.urandom(4).hex()}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "correcthorse123", "name": "Reviewer Owner"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    user_data = client.get("/api/auth/me", headers=auth_header(token)).json()
    return {"token": token, "email": email, "id": user_data["id"]}


def _create_test_recording(client, token: str, tmp_path: Path) -> str:
    import numpy as np
    import soundfile as sf
    sr = 22050
    t = np.linspace(0, 1.0, sr)
    sig = 0.3 * np.sin(2 * np.pi * 320.0 * t)
    wav_file = tmp_path / f"test_{os.urandom(3).hex()}.wav"
    sf.write(str(wav_file), sig, sr)

    with wav_file.open("rb") as fh:
        res = client.post("/api/recordings/quick-analyze", headers=auth_header(token), files={"file": ("test.wav", fh, "audio/wav")})
    assert res.status_code == 200
    return res.json()["id"]


def test_annotation_with_reviewer_flags_and_audit_trail(client, auth_user, tmp_path):
    hdr = auth_header(auth_user["token"])
    rec_id = _create_test_recording(client, auth_user["token"], tmp_path)

    payload = {
        "reviewer_id": "vet_ethologist_01",
        "vocalization_label": "bark",
        "context_label": "alert",
        "uncertain_classification": True,
        "multiple_vocalizations": True,
        "notes": "Low confidence due to room reverberation",
    }
    res = client.post(f"/api/recordings/{rec_id}/annotations", headers=hdr, json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["recording_id"] == rec_id
    assert len(body["annotations"]) == 1
    ann = body["annotations"][0]
    assert ann["reviewer_id"] == "vet_ethologist_01"
    assert ann["uncertain_classification"] is True
    assert ann["multiple_vocalizations"] is True
    assert ann["canonical_label"] == "bark"
    assert "annotation_id" in ann
    assert ann["annotation_version"] == "2.0"
    assert ann["reviewer_user_id"] == auth_user["id"]


def test_reviewer_cannot_overwrite_another_reviewer_annotation(client, auth_user, tmp_path):
    hdr = auth_header(auth_user["token"])
    rec_id = _create_test_recording(client, auth_user["token"], tmp_path)

    # First reviewer annotation
    r1 = client.post(
        f"/api/recordings/{rec_id}/annotations",
        headers=hdr,
        json={"reviewer_id": "dr_smith", "vocalization_label": "bark"},
    )
    assert r1.status_code == 200

    # Second reviewer annotation (different reviewer_id)
    r2 = client.post(
        f"/api/recordings/{rec_id}/annotations",
        headers=hdr,
        json={"reviewer_id": "dr_jones", "vocalization_label": "whine"},
    )
    assert r2.status_code == 200
    anns = r2.json()["annotations"]
    assert len(anns) == 2
    reviewers = {a["reviewer_id"] for a in anns}
    assert reviewers == {"dr_smith", "dr_jones"}
    # Disagreement is visible
    assert r2.json()["consensus_label"] == "disputed"


def test_cohens_kappa_sample_size_and_disagreement_reporting(client, auth_user, tmp_path):
    hdr = auth_header(auth_user["token"])
    rec1 = _create_test_recording(client, auth_user["token"], tmp_path)
    rec2 = _create_test_recording(client, auth_user["token"], tmp_path)

    # Rec1: Agreement (growl / growl)
    client.post(f"/api/recordings/{rec1}/annotations", headers=hdr, json={"reviewer_id": "rev_a", "vocalization_label": "growl"})
    client.post(f"/api/recordings/{rec1}/annotations", headers=hdr, json={"reviewer_id": "rev_b", "vocalization_label": "growl"})

    # Rec2: Disagreement (howl / whine)
    client.post(f"/api/recordings/{rec2}/annotations", headers=hdr, json={"reviewer_id": "rev_a", "vocalization_label": "howl"})
    client.post(f"/api/recordings/{rec2}/annotations", headers=hdr, json={"reviewer_id": "rev_b", "vocalization_label": "whine"})

    cons = client.get("/api/recordings/annotations/consensus", headers=hdr).json()
    assert cons["total_dual_annotated"] == 2
    assert cons["observed_agreement"] == 0.5
    assert "disagreements_count" in cons
    assert cons["disagreements_count"] == 1
    assert len(cons["disagreement_cases"]) == 1
    assert cons["disagreement_cases"][0]["recording_id"] == rec2
    # Small sample warning must be explicitly surfaced
    assert "N=2 < 30" in cons["sample_size_assessment"]
    assert "confidence_interval_95" in cons
    assert "pabak" in cons
    # Reviewer independence audit tracks whether reviews were single-user account simulated
    assert cons["reviewer_independence_status"] == "unverified_single_account_simulation"
