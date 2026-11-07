from pathlib import Path

import numpy as np

from app.services.audio import AudioError, assess_quality, preprocess
from app.services.classifier import classify
from app.services.explain import explain
from app.services.features import extract_features
from app.services.intent import interpret
from app.services.synthesis import synthesize
from tests.conftest import auth_header, write_bursts, write_tone


def test_silence_rejected():
    y = np.zeros(22050, dtype=np.float32)
    q = assess_quality(y, 22050)
    assert q["status"] == "reject"


def test_preprocess_mono_resample():
    y = np.stack([np.ones(8000), np.zeros(8000)], axis=1).astype(np.float32)
    out, meta = preprocess(y, 8000)
    assert out.ndim == 1
    assert meta["target_sr"] == 22050
    assert out.size > 8000


def test_howl_like_tone_not_random():
    sr = 22050
    t = np.arange(int(sr * 2.5)) / sr
    f0 = 420 + 80 * np.sin(2 * np.pi * 0.4 * t)
    y = 0.2 * np.sin(2 * np.pi * f0 * t).astype(np.float32)
    feats = extract_features(y, sr)
    result = classify(feats, {"status": "ok"})
    # A long tonal signal should not be called a yip.
    assert result["vocalization"] != "yip"
    assert feats["duration"] > 2.0


def test_burst_sequence_not_howl():
    sr = 22050
    rng = np.random.default_rng(2)
    pieces = []
    for _ in range(5):
        n = int(0.14 * sr)
        burst = rng.normal(0, 1, n).astype(np.float32)
        env = np.exp(-np.linspace(0, 4, n))
        pieces.append(burst * env * 0.6)
        pieces.append(np.zeros(int(0.2 * sr), dtype=np.float32))
    y = np.concatenate(pieces)
    feats = extract_features(y, sr)
    result = classify(feats, {"status": "ok"})
    assert result["vocalization"] != "howl"


def test_unknown_on_reject_quality():
    feats = extract_features(np.zeros(22050, dtype=np.float32), 22050)
    result = classify(feats, {"status": "reject", "reasons": ["silent"]})
    assert result["abstained"] is True
    assert result["vocalization"] == "unknown"


def test_engine_a_missing_invalid_and_event_free_abstention():
    # 1. Missing measurements
    r_missing = classify({}, {"status": "ok"})
    assert r_missing["abstained"] is True
    assert r_missing["vocalization"] == "unknown"

    # 2. Invalid (NaN / Inf) measurements
    r_nan = classify(
        {
            "duration": 1.0,
            "rms": float("nan"),
            "centroid_mean": 1000.0,
            "flatness_mean": 0.1,
            "zcr_mean": 0.05,
            "event_count": 2,
        },
        {"status": "ok"},
    )
    assert r_nan["abstained"] is True
    assert r_nan["vocalization"] == "unknown"

    # 3. No detected events (event_count == 0)
    r_no_events = classify(
        {
            "duration": 1.0,
            "rms": 0.05,
            "centroid_mean": 1000.0,
            "flatness_mean": 0.1,
            "zcr_mean": 0.05,
            "event_count": 0,
        },
        {"status": "ok"},
    )
    assert r_no_events["abstained"] is True
    assert r_no_events["vocalization"] == "unknown"
    assert "event" in (r_no_events["abstain_reason"] or "").lower()

    # 4. Explain reports unavailable measurements honestly
    expl = explain(
        {"duration": 1.0, "rms": 0.05, "f0_mean": 0.0, "event_count": 0},
        {"status": "ok"},
        r_no_events,
        {"context": "insufficient_evidence", "insufficient_evidence": True},
    )
    f0_ev = next(e for e in expl["acoustic_evidence"] if e["feature"] == "f0_mean")
    assert f0_ev["available"] is False
    assert f0_ev["value"] == "Unavailable"


def test_intent_come_and_ambiguous():
    one = interpret("come here")
    assert one["intent"] == "come"
    assert one["mapping"]["status"] == "experimental"
    amb = interpret("come here and stay and play")
    assert amb["intent"] == "ambiguous"
    assert amb["needs_clarification"] is True


def test_synth_is_finite_and_distinct():
    lengths = {}
    for name in ("bark", "howl", "yip", "growl"):
        y, params = synthesize(name)
        assert np.isfinite(y).all()
        assert y.size > 100
        assert params["synthetic"] is True
        lengths[name] = y.size
    assert lengths["howl"] > lengths["yip"] * 4


def test_analyze_endpoint_real_inference_and_media(client, user_a, tmp_path):
    wav = write_bursts(tmp_path / "x.wav")
    with wav.open("rb") as fh:
        res = client.post(
            "/api/recordings/analyze",
            headers=auth_header(user_a["token"]),
            files={"file": ("x.wav", fh, "audio/wav")},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    rec_id = body["id"]
    assert "analysis" in body
    analysis = body["analysis"]
    assert analysis["model_version"]
    assert analysis["scientific_validation_status"] == "unvalidated_heuristic"
    assert analysis["vocalization"] in {
        "bark",
        "growl",
        "whine",
        "howl",
        "yip",
        "grunt",
        "other",
        "unknown",
    }
    assert "limitations" in analysis
    assert analysis["explanation"]["acoustic_evidence"]

    # Immediate follow-up media & spectrogram-data fetches must succeed (200 OK)
    for kind in ("waveform", "spectrogram", "processed", "original"):
        m = client.get(f"/api/recordings/{rec_id}/media/{kind}", headers=auth_header(user_a["token"]))
        assert m.status_code == 200, f"media/{kind} failed: {m.text}"
    sd = client.get(f"/api/recordings/{rec_id}/spectrogram-data", headers=auth_header(user_a["token"]))
    assert sd.status_code == 200
    assert sd.json()["valid"] is True

    # Must not claim the 90% target is met.
    health = client.get("/api/health").json()
    assert health["accuracy_target_met"] is False


def test_unsupported_upload(client, user_a, tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("not audio")
    with p.open("rb") as fh:
        res = client.post(
            "/api/recordings/analyze",
            headers=auth_header(user_a["token"]),
            files={"file": ("x.txt", fh, "text/plain")},
        )
    assert res.status_code == 400


def test_high_freq_toy_squeak_classified_other():
    sr = 22050
    t = np.arange(int(sr * 0.9)) / sr
    y = (0.35 * np.sin(2 * np.pi * 4200 * t) + 0.25 * np.sin(2 * np.pi * 6400 * t)).astype(np.float32)
    feats = extract_features(y, sr)
    result = classify(feats, {"status": "ok"})
    assert result["vocalization"] == "other"


def test_long_bark_train_not_howl():
    sr = 22050
    y, _ = synthesize("bark", sr=sr, duration_sec=4.5)
    feats = extract_features(y, sr)
    result = classify(feats, {"status": "ok"})
    assert result["vocalization"] == "bark"
