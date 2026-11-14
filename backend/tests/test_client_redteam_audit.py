"""Red-team security, integrity, clinical safety, and DSP verification suite."""

from __future__ import annotations

import base64
import io
import json
import os
import struct
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import numpy as np
import soundfile as sf

from app import security
from app.services import breed_intelligence as breed_intel_mod
from app.services.synthesis import _two_pole_resonator
from tests.conftest import auth_header, write_bursts


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_corrupt_1gb_wav_64b() -> bytes:
    """Construct a 64-byte RIFF/WAVE header claiming a 1 GiB data payload."""
    riff = b"RIFF" + struct.pack("<I", 0x40000024) + b"WAVE"
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
    data_hdr = b"data" + struct.pack("<I", 1024**3)
    payload = riff + fmt + data_hdr
    return (payload + b"\x00" * 64)[:64]


def _write_clean_harmonic_wav(path: Path, sr: int = 22050, dur: float = 1.2, f0: float = 340.0) -> Path:
    t = np.arange(int(sr * dur)) / sr
    env = np.where((t % 0.4) < 0.16, np.sin(np.pi * np.clip((t % 0.4) / 0.16, 0.0, 1.0)), 0.01)
    y = env * (0.45 * np.sin(2 * np.pi * f0 * t) + 0.18 * np.sin(2 * np.pi * 2 * f0 * t))
    sf.write(str(path), y.astype(np.float32), sr)
    return path


def _write_noisy_burst_wav(path: Path, sr: int = 22050, dur: float = 1.2) -> Path:
    rng = np.random.default_rng(42)
    t = np.arange(int(sr * dur)) / sr
    env = np.where((t % 0.3) < 0.15, 0.42, 0.18)
    y = env * rng.normal(0.0, 0.35, size=t.shape) + 0.05 * np.sin(2 * np.pi * 260.0 * t)
    sf.write(str(path), np.clip(y, -0.75, 0.75).astype(np.float32), sr)
    return path


def test_audio_upload_security_and_fuzzing(client, user_a):
    headers = auth_header(user_a["token"])
    vectors = [
        ("truncated_8b.wav", b"RIFF\x24\x00\x00\x00", "audio/wav"),
        ("corrupt_1gb.wav", _build_corrupt_1gb_wav_64b(), "audio/wav"),
        ("empty.wav", b"", "audio/wav"),
        ("pe_exec.wav", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 48, "audio/wav"),
        ("elf_bin.wav", b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56, "audio/wav"),
        ("polyglot.wav", b"RIFF\x24\x00\x00\x00WAVE<script>alert(1)</script>" + b"\x00" * 32, "audio/wav"),
        ("garbage_id3.mp3", b"ID3\x04\x00\x00\x00\x00\x00\x10" + os.urandom(128), "audio/mpeg"),
    ]

    for fname, raw, mime in vectors:
        res = client.post(
            "/api/recordings/quick-analyze",
            headers=headers,
            files={"file": (fname, io.BytesIO(raw), mime)},
        )
        assert res.status_code in (400, 422), f"{fname} returned {res.status_code}: {res.text}"
        assert "Traceback" not in res.text


def test_jwt_tampering_and_alg_none_rejection(client, user_a):
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": user_a["user"]["id"],
            "email": user_a["email"],
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )

    h_b64, _p_b64, sig_b64 = user_a["token"].split(".")
    tampered_payload = _b64url(
        json.dumps(
            {
                "sub": "forged-other-user-id",
                "email": "attacker@example.com",
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
        ).encode("utf-8")
    )
    tampered_token = f"{h_b64}.{tampered_payload}.{sig_b64}"

    alg_none_header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    alg_none_payload = _b64url(
        json.dumps(
            {
                "sub": user_a["user"]["id"],
                "email": user_a["email"],
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
        ).encode("utf-8")
    )
    alg_none_token = f"{alg_none_header}.{alg_none_payload}."

    for bad_token in (expired_token, tampered_token, alg_none_token):
        hdrs = auth_header(bad_token)
        assert client.get("/api/dogs", headers=hdrs).status_code == 401
        assert client.get("/api/recordings", headers=hdrs).status_code == 401


def test_multi_user_idor_and_persistence_isolation(client, user_a, user_b, tmp_path: Path):
    hdr_a = auth_header(user_a["token"])
    hdr_b = auth_header(user_b["token"])

    dog_res = client.post(
        "/api/dogs",
        headers=hdr_a,
        json={"name": "Apollo", "breed": "Golden Retriever", "sex": "male", "weight_kg": 30.0},
    )
    assert dog_res.status_code == 201, dog_res.text
    dog_a_id = dog_res.json()["id"]

    wav_path = write_bursts(tmp_path / "idor_rec.wav")
    with wav_path.open("rb") as fh:
        rec_res = client.post(
            "/api/recordings/analyze",
            headers=hdr_a,
            data={"dog_id": dog_a_id},
            files={"file": ("idor_rec.wav", fh, "audio/wav")},
        )
    assert rec_res.status_code == 200, rec_res.text
    rec_a_id = rec_res.json()["id"]

    # Cross-tenant Dog IDOR checks
    assert client.get(f"/api/dogs/{dog_a_id}", headers=hdr_b).status_code == 404
    assert (
        client.patch(
            f"/api/dogs/{dog_a_id}",
            headers=hdr_b,
            json={"name": "Hijacked", "breed": "Pug", "sex": "female"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/dogs/{dog_a_id}", headers=hdr_b).status_code == 404

    # Cross-tenant Recording & attachment IDOR checks
    with wav_path.open("rb") as fh:
        assert (
            client.post(
                "/api/recordings/quick-analyze",
                headers=hdr_b,
                data={"dog_id": dog_a_id},
                files={"file": ("idor_rec.wav", fh, "audio/wav")},
            ).status_code
            == 404
        )
    assert client.get(f"/api/recordings/{rec_a_id}", headers=hdr_b).status_code == 404
    assert client.delete(f"/api/recordings/{rec_a_id}", headers=hdr_b).status_code == 404
    assert (
        client.post(
            f"/api/recordings/{rec_a_id}/annotations",
            headers=hdr_b,
            json={"reviewer_id": "intruder", "vocalization_label": "howl"},
        ).status_code
        == 404
    )

    # Confirm User A's records remain untouched
    assert client.get(f"/api/dogs/{dog_a_id}", headers=hdr_a).status_code == 200
    assert client.get(f"/api/recordings/{rec_a_id}", headers=hdr_a).status_code == 200


def test_fifo_10_dog_cap_and_gender_dimorphism(client, tmp_path: Path, monkeypatch):
    reg = client.post(
        "/api/auth/register",
        json={"email": f"fifo-{os.urandom(4).hex()}@example.com", "password": "correcthorse", "name": "FIFO"},
    )
    assert reg.status_code == 200, reg.text
    hdr = auth_header(reg.json()["access_token"])

    created_names = [f"FIFO-{i:02d}" for i in range(11)]
    for name in created_names:
        r = client.post(
            "/api/dogs",
            headers=hdr,
            json={"name": name, "breed": "Beagle", "sex": "male", "weight_kg": 11.5},
        )
        assert r.status_code == 201, r.text
        time.sleep(0.002)

    dogs_after = client.get("/api/dogs", headers=hdr).json()
    assert len(dogs_after) == 8
    remaining_names = {d["name"] for d in dogs_after}
    for pruned in created_names[:3]:
        assert pruned not in remaining_names
    for kept in created_names[3:]:
        assert kept in remaining_names

    # Spy on resolve_breed_intelligence while running quick-analyze for male vs female dogs
    seen_sexes: list[str | None] = []
    orig_resolve = breed_intel_mod.resolve_breed_intelligence

    def spy_resolve(*args, **kwargs):
        seen_sexes.append(kwargs.get("sex"))
        return orig_resolve(*args, **kwargs)

    monkeypatch.setattr(breed_intel_mod, "resolve_breed_intelligence", spy_resolve)

    male_res = client.post(
        "/api/dogs",
        headers=hdr,
        json={"name": "MaxMale", "breed": "Beagle", "sex": "male", "weight_kg": 12.0},
    )
    female_res = client.post(
        "/api/dogs",
        headers=hdr,
        json={"name": "BellaFemale", "breed": "Beagle", "sex": "female", "weight_kg": 12.0},
    )
    assert male_res.status_code == 201 and female_res.status_code == 201
    male_id = male_res.json()["id"]
    female_id = female_res.json()["id"]

    clean_wav = _write_clean_harmonic_wav(tmp_path / "clean_harmonic.wav")
    noisy_wav = _write_noisy_burst_wav(tmp_path / "noisy_burst.wav")

    with clean_wav.open("rb") as fh:
        qa_male = client.post(
            "/api/recordings/quick-analyze",
            headers=hdr,
            data={"dog_id": male_id},
            files={"file": ("clean_harmonic.wav", fh, "audio/wav")},
        )
    with noisy_wav.open("rb") as fh:
        qa_female = client.post(
            "/api/recordings/quick-analyze",
            headers=hdr,
            data={"dog_id": female_id},
            files={"file": ("noisy_burst.wav", fh, "audio/wav")},
        )

    assert qa_male.status_code == 200 and qa_female.status_code == 200
    assert "male" in seen_sexes and "female" in seen_sexes

    d_male = qa_male.json()
    d_female = qa_female.json()
    assert d_male["dog_profile"]["sex"] == "male"
    assert d_female["dog_profile"]["sex"] == "female"

    # Gender dimorphism F0 & formant calibration
    male_prior = orig_resolve("Beagle", 12.0, sex="male")
    female_prior = orig_resolve("Beagle", 12.0, sex="female")
    assert male_prior["vocalization_profile"]["optimal_synth_pitch_hz"] < female_prior["vocalization_profile"]["optimal_synth_pitch_hz"]
    assert male_prior["allometric_acoustic_prior"]["sex_multiplier"] == 0.91
    assert female_prior["allometric_acoustic_prior"]["sex_multiplier"] == 1.08

    # Dynamic (non-hardcoded) SNR & HNR computation across distinct waveforms
    snr_clean = d_male["analysis"]["features"]["snr_db"]
    hnr_clean = d_male["analysis"]["features"]["hnr"]
    snr_noisy = d_female["analysis"]["features"]["snr_db"]
    hnr_noisy = d_female["analysis"]["features"]["hnr"]
    assert (snr_clean, hnr_clean) != (22.5, 11.2)
    assert (snr_noisy, hnr_noisy) != (22.5, 11.2)
    assert snr_clean != snr_noisy
    assert hnr_clean != hnr_noisy


def test_dual_reviewer_cohens_kappa_consensus(client, tmp_path: Path):
    reg = client.post(
        "/api/auth/register",
        json={"email": f"kappa-{os.urandom(4).hex()}@example.com", "password": "correcthorse", "name": "Kappa"},
    )
    assert reg.status_code == 200, reg.text
    hdr = auth_header(reg.json()["access_token"])

    w1 = _write_clean_harmonic_wav(tmp_path / "k1.wav", f0=320.0)
    w2 = _write_noisy_burst_wav(tmp_path / "k2.wav")
    with w1.open("rb") as fh:
        r1 = client.post("/api/recordings/quick-analyze", headers=hdr, files={"file": ("k1.wav", fh, "audio/wav")})
    with w2.open("rb") as fh:
        r2 = client.post("/api/recordings/quick-analyze", headers=hdr, files={"file": ("k2.wav", fh, "audio/wav")})
    assert r1.status_code == 200 and r2.status_code == 200
    rec1_id = r1.json()["id"]
    rec2_id = r2.json()["id"]

    # Agreement on rec1 (bark/bark) & agreement on rec2 (growl/growl) -> kappa == 1.0
    for rec_id, lbl in ((rec1_id, "bark"), (rec2_id, "growl")):
        a1 = client.post(
            f"/api/recordings/{rec_id}/annotations",
            headers=hdr,
            json={"reviewer_id": "reviewer_1", "vocalization_label": lbl, "context_label": "play"},
        )
        a2 = client.post(
            f"/api/recordings/{rec_id}/annotations",
            headers=hdr,
            json={"reviewer_id": "reviewer_2", "vocalization_label": lbl, "context_label": "play"},
        )
        assert a1.status_code == 200 and a2.status_code == 200

    cons = client.get("/api/recordings/annotations/consensus", headers=hdr)
    assert cons.status_code == 200, cons.text
    body = cons.json()
    assert body["total_dual_annotated"] == 2
    assert -1.0 <= body["cohens_kappa"] <= 1.0
    assert body["cohens_kappa"] == 1.0
    assert body["consensus_status"] == "strong_consensus"


def test_resonator_exact_formant_peaks():
    sr = 22050
    n_fft = 4096
    impulse = np.zeros(n_fft, dtype=np.float64)
    impulse[0] = 1.0
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)

    for target_hz, bw_hz in ((620.0, 170.0), (1450.0, 260.0)):
        h = _two_pole_resonator(impulse, sr=sr, freq=target_hz, bw=bw_hz)
        spec = np.abs(np.fft.rfft(h, n=n_fft))
        peak_hz = float(freqs[int(np.argmax(spec))])
        assert abs(peak_hz - target_hz) <= 5.5, f"Peak {peak_hz:.2f} Hz drifted from {target_hz} Hz"
