"""Priority 8 Automated Communicator Audio Test Matrix.

Verifies all 10 Engine B Communicator vocal patterns across direct DSP synthesis,
API `/api/communicate/generate` + `/audio` download, burst structure, zero-click
continuity, DC offset elimination, distinct acoustic signatures, and dog-profile
pitch adaptation.
"""

from __future__ import annotations

import io
import numpy as np
import pytest
import soundfile as sf

from app.services.synthesis import calculate_synthesis_parameters, synthesize
from tests.conftest import auth_header


AUDIO_MATRIX: list[tuple[str, str, str | None, dict]] = [
    ("correction_grumble_2_bursts", "correction_grumble", "stop", {}),
    ("warning_growl", "growl", None, {}),
    ("attention_whine", "whine", "attention", {}),
    ("friendly_social", "whimper", "positive_reinforcement", {}),
    ("play_invitation", "yip", "play", {}),
    ("alert_bark", "bark", "come", {}),
    ("contact_howl", "howl", "calm", {}),
    ("short_yip", "yelp", None, {}),
    ("multi_burst_pant", "pant", None, {}),
    ("long_duration_howl", "howl", None, {"duration_sec": 2.6}),
]


def _measure_pcm(y: np.ndarray, sr: int) -> dict[str, float | int]:
    y = np.asarray(y, dtype=np.float64)
    rms = float(np.sqrt(np.mean(y**2)))
    peak = float(np.max(np.abs(y)))
    dc = float(np.mean(y))
    clipped = int(np.sum(np.abs(y) > 0.99))
    diffs = np.abs(np.diff(y))
    max_step = float(np.max(diffs))
    click_thresh = max(0.72, peak * 1.25)
    abrupt_clicks = int(np.sum(diffs > click_thresh))
    edge_jump = float(max(abs(y[0]), abs(y[-1])))

    spec = np.abs(np.fft.rfft(y * np.hanning(y.size))) + 1e-12
    freqs = np.fft.rfftfreq(y.size, d=1.0 / sr)
    centroid = float(np.sum(freqs * spec) / np.sum(spec))
    geo_mean = float(np.exp(np.mean(np.log(spec))))
    flatness = float(geo_mean / np.mean(spec))

    return {
        "rms": rms,
        "peak": peak,
        "dc_offset": dc,
        "clipped_count": clipped,
        "max_sample_step": max_step,
        "abrupt_clicks": abrupt_clicks,
        "edge_jump": edge_jump,
        "spectral_centroid_hz": centroid,
        "spectral_flatness": flatness,
    }


@pytest.mark.parametrize("pattern_id,vocalization,intent,extra", AUDIO_MATRIX)
def test_direct_dsp_matrix_clean_continuous_and_deterministic(pattern_id: str, vocalization: str, intent: str | None, extra: dict):
    y1, params1 = synthesize(vocalization=vocalization, intent=intent, **extra)
    y2, params2 = synthesize(vocalization=vocalization, intent=intent, **extra)

    assert y1.ndim == 1
    assert y1.size == params1["sample_count"]
    assert params1["sr"] == 22050
    assert np.isfinite(y1).all()
    assert np.array_equal(y1, y2), f"{pattern_id} synthesis must be deterministic"

    m = _measure_pcm(y1, 22050)
    assert m["rms"] >= 0.03, f"{pattern_id} unexpectedly silent (rms={m['rms']})"
    assert 0.20 <= m["peak"] <= 0.95, f"{pattern_id} peak out of range ({m['peak']})"
    assert abs(m["dc_offset"]) < 0.005, f"{pattern_id} excessive DC offset ({m['dc_offset']})"
    assert m["clipped_count"] == 0, f"{pattern_id} clipped {m['clipped_count']} samples"
    assert m["edge_jump"] < 0.02, f"{pattern_id} non-zero boundary jump ({m['edge_jump']})"
    assert m["abrupt_clicks"] <= 2, f"{pattern_id} has {m['abrupt_clicks']} click discontinuities"
    assert params2["sample_count"] == params1["sample_count"]


@pytest.mark.parametrize("pattern_id,vocalization,intent,extra", AUDIO_MATRIX)
def test_api_communicate_generate_and_audio_stream_matrix(client, user_a, pattern_id: str, vocalization: str, intent: str | None, extra: dict):
    headers = auth_header(user_a["token"])
    payload = {
        "text": f"test cue {pattern_id.replace('_', ' ')}",
        "intent_override": intent or "attention",
        "vocalization_target": vocalization,
        "generation_method": "experimental_dsp",
        **extra,
    }
    res = client.post("/api/communicate/generate", headers=headers, json=payload)
    assert res.status_code == 200, f"{pattern_id}: {res.text}"
    body = res.json()
    gen = body["generated"]
    audio_url = (gen.get("media_urls") or {}).get("audio") or gen.get("audio_url")
    assert audio_url

    wav_resp = client.get(audio_url, headers=headers)
    assert wav_resp.status_code == 200
    assert wav_resp.content[:4] == b"RIFF"

    y, sr = sf.read(io.BytesIO(wav_resp.content), dtype="float32")
    assert sr == 22050
    assert y.ndim == 1
    m = _measure_pcm(y, sr)
    assert m["clipped_count"] == 0
    assert m["abrupt_clicks"] <= 2
    assert abs(m["dc_offset"]) < 0.005


def test_correction_grumble_two_coherent_bursts_and_no_fragmentation():
    y, params = synthesize(vocalization="correction_grumble", intent="stop")
    assert params["vocalization"] == "growl"
    assert params["intent"] == "stop"
    assert params["n_events"] == 2
    assert params["gap_sec"] == pytest.approx(0.11, abs=0.01)

    sr = params["sr"]
    m = _measure_pcm(y, sr)
    assert m["max_sample_step"] <= 0.25, f"Unnatural jump detected: {m['max_sample_step']}"
    assert m["spectral_flatness"] <= 0.08, f"Too noisy/broken (flatness={m['spectral_flatness']})"
    assert m["spectral_centroid_hz"] < 1200.0, f"Unexpectedly harsh high energy ({m['spectral_centroid_hz']})"

    # Verify two coherent active voiced regions with a quiet pause in between
    win = int(0.025 * sr)
    hop = int(0.010 * sr)
    frame_rms = np.array([
        float(np.sqrt(np.mean(y[i : i + win] ** 2)))
        for i in range(0, y.size - win, hop)
    ])
    burst1_peak_rms = float(np.max(frame_rms[: len(frame_rms) // 2]))
    mid_start = int(0.40 * len(frame_rms))
    mid_end = int(0.60 * len(frame_rms))
    mid_gap_min_rms = float(np.min(frame_rms[mid_start:mid_end]))
    burst2_peak_rms = float(np.max(frame_rms[len(frame_rms) // 2 :]))

    assert burst1_peak_rms >= 0.08
    assert burst2_peak_rms >= 0.08
    assert mid_gap_min_rms < 0.02, f"Expected clean intentional pause between bursts, got {mid_gap_min_rms}"


def test_acoustic_signatures_differ_across_patterns():
    y_growl, _ = synthesize("correction_grumble", "stop")
    y_whine, _ = synthesize("whine", "attention")
    y_short, _ = synthesize("yelp", None)
    y_long, _ = synthesize("howl", None, duration_sec=2.6)

    m_growl = _measure_pcm(y_growl, 22050)
    m_whine = _measure_pcm(y_whine, 22050)
    assert m_whine["spectral_centroid_hz"] > m_growl["spectral_centroid_hz"] + 350.0
    assert (y_long.size / 22050.0) >= 2.4
    assert (y_short.size / 22050.0) <= 0.5


def test_dog_profile_pitch_scaling_explicitly_logged_as_heuristic(client, user_a):
    headers = auth_header(user_a["token"])
    small_dog = client.post(
        "/api/dogs",
        headers=headers,
        json={"name": "Pip", "breed": "Chihuahua", "sex": "female", "weight_kg": 4.2},
    ).json()
    large_dog = client.post(
        "/api/dogs",
        headers=headers,
        json={"name": "Titan", "breed": "Rottweiler", "sex": "male", "weight_kg": 48.0},
    ).json()

    r_small = client.post(
        "/api/communicate/generate",
        headers=headers,
        json={
            "text": "stop leave it",
            "dog_id": small_dog["id"],
            "intent_override": "stop",
            "vocalization_target": "correction_grumble",
            "generation_method": "experimental_dsp",
        },
    ).json()
    r_large = client.post(
        "/api/communicate/generate",
        headers=headers,
        json={
            "text": "stop leave it",
            "dog_id": large_dog["id"],
            "intent_override": "stop",
            "vocalization_target": "correction_grumble",
            "generation_method": "experimental_dsp",
        },
    ).json()

    p_small = r_small["generated"]["params"]
    p_large = r_large["generated"]["params"]
    assert p_small["f0_base_hz"] > p_large["f0_base_hz"]
    assert p_small["dog_profile_pitch_scaling"]["calibration_type"] == "heuristic_morphology_estimate"
    # Direct calculate_synthesis_parameters check
    p_alias = calculate_synthesis_parameters("correction_grumble")
    assert p_alias["vocalization"] == "growl"
    assert p_alias["n_events"] == 2
