from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.services.spectrogram import SpectrogramError, compute_spectrogram, compute_spectrogram_from_file
from app.services.synthesis import (
    SUPPORTED_PROFILES,
    calculate_synthesis_parameters,
    synthesize,
    validate_generated_wav,
)


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_every_synthesis_profile_valid_and_deterministic(profile: str, tmp_path: Path):
    y1, p1 = synthesize(profile, intent="come", sr=22050)
    y2, p2 = synthesize(profile, intent="come", sr=22050)

    # Deterministic: identical inputs must produce bit-identical waveforms and parameters
    assert np.array_equal(y1, y2)
    assert p1["seed"] == p2["seed"]
    assert p1["sr"] == 22050
    assert np.isfinite(y1).all()
    assert y1.size == int(round(22050 * p1["duration"]))

    # Non-silent and within safe normalization bounds (no clipping)
    rms = float(np.sqrt(np.mean(y1**2)))
    peak = float(np.max(np.abs(y1)))
    assert rms > 1e-3
    assert 0.1 < peak <= 0.92
    assert float(np.mean(np.abs(y1) > 0.99)) == 0.0

    # Encode to WAV and run full disk validation
    wav_path = tmp_path / f"{profile}.wav"
    sf.write(str(wav_path), y1, 22050, subtype="PCM_16")
    val = validate_generated_wav(wav_path, expected_sr=22050)
    assert val["valid"] is True
    assert val["sample_rate"] == 22050
    assert val["channels"] == 1
    assert val["sample_count"] == y1.size
    assert val["non_silent"] is True
    assert len(val["sha256"]) == 64


def test_synthesis_parameter_bounds_validation():
    with pytest.raises(ValueError):
        calculate_synthesis_parameters("bark", duration_sec=0.01)
    with pytest.raises(ValueError):
        calculate_synthesis_parameters("bark", duration_sec=12.0)
    with pytest.raises(ValueError):
        calculate_synthesis_parameters("bark", intensity=0.02)
    with pytest.raises(ValueError):
        calculate_synthesis_parameters("bark", pitch_hz=5000.0)


def test_spectrogram_single_frequency_sine():
    sr = 22050
    t = np.arange(sr) / sr
    y = (0.6 * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32)
    res = compute_spectrogram(y, sr=sr)
    assert res["valid"] is True
    metrics = res["signal_metrics"]
    assert metrics["is_silent"] is False
    # Peak frequency must match 1000 Hz within 1 STFT bin (~21.5 Hz)
    assert abs(metrics["peak_freq_hz"] - 1000.0) <= 25.0


def test_spectrogram_two_frequency_signal():
    sr = 22050
    t = np.arange(sr) / sr
    y = (0.5 * np.sin(2 * np.pi * 500.0 * t) + 0.4 * np.sin(2 * np.pi * 2000.0 * t)).astype(np.float32)
    res = compute_spectrogram(y, sr=sr)
    metrics = res["signal_metrics"]
    peaks = sorted([metrics["peak_freq_hz"], metrics["secondary_freq_hz"] or 0.0])
    assert abs(peaks[0] - 500.0) <= 30.0
    assert abs(peaks[1] - 2000.0) <= 30.0


def test_spectrogram_frequency_sweep():
    sr = 22050
    dur = 1.0
    t = np.arange(int(sr * dur)) / sr
    # Linear chirp from 300 Hz to 3000 Hz
    f0, f1 = 300.0, 3000.0
    phase = 2 * np.pi * (f0 * t + 0.5 * ((f1 - f0) / dur) * t**2)
    y = (0.5 * np.sin(phase)).astype(np.float32)
    res = compute_spectrogram(y, sr=sr)
    frame_peaks = res["signal_metrics"]["frame_peak_freqs_hz"]
    assert len(frame_peaks) >= 6
    # Early frames must be much lower frequency than late frames
    assert np.mean(frame_peaks[:3]) < 900.0
    assert np.mean(frame_peaks[-3:]) > 2100.0


def test_spectrogram_impulse_and_white_noise():
    sr = 22050
    impulse = np.zeros(sr // 2, dtype=np.float32)
    impulse[len(impulse) // 2] = 0.9
    res_imp = compute_spectrogram(impulse, sr=sr)
    assert res_imp["signal_metrics"]["is_silent"] is False
    assert res_imp["signal_metrics"]["spectral_flatness"] > 0.35

    rng = np.random.default_rng(42)
    noise = (0.25 * rng.normal(0, 1, sr // 2)).astype(np.float32)
    res_noise = compute_spectrogram(noise, sr=sr)
    assert res_noise["signal_metrics"]["spectral_flatness"] > 0.45


def test_spectrogram_silence_and_near_silence():
    sr = 22050
    silent = np.zeros(sr // 2, dtype=np.float32)
    res_sil = compute_spectrogram(silent, sr=sr)
    assert res_sil["signal_metrics"]["is_silent"] is True
    assert res_sil["signal_metrics"]["peak_freq_hz"] is None
    assert np.max(res_sil["grid"]["db"]) == -80.0

    t = np.arange(sr // 2) / sr
    near_silent = (3e-4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    res_near = compute_spectrogram(near_silent, sr=sr)
    assert res_near["signal_metrics"]["is_silent"] is False
    assert res_near["signal_metrics"]["is_near_silent"] is True


def test_spectrogram_clipped_stereo_short_and_invalid(tmp_path: Path):
    sr = 22050
    t = np.arange(sr // 2) / sr
    clipped = np.clip(2.5 * np.sin(2 * np.pi * 440.0 * t), -1.0, 1.0).astype(np.float32)
    res_clip = compute_spectrogram(clipped, sr=sr)
    assert res_clip["signal_metrics"]["is_clipped"] is True
    assert res_clip["signal_metrics"]["clipping_ratio"] > 0.1

    # Stereo input
    stereo = np.stack([0.4 * np.sin(2 * np.pi * 600.0 * t), 0.4 * np.sin(2 * np.pi * 600.0 * t)], axis=1).astype(
        np.float32
    )
    res_st = compute_spectrogram(stereo, sr=sr)
    assert res_st["original_channels"] == 2
    assert res_st["analysis_channels"] == 1
    assert abs(res_st["signal_metrics"]["peak_freq_hz"] - 600.0) <= 25.0

    # Very short valid audio (128 samples)
    short_y = (0.5 * np.sin(2 * np.pi * 1000.0 * np.arange(128) / sr)).astype(np.float32)
    res_short = compute_spectrogram(short_y, sr=sr)
    assert res_short["valid"] is True

    # Too short (< 16 samples)
    with pytest.raises(SpectrogramError):
        compute_spectrogram(np.zeros(8, dtype=np.float32), sr=sr)

    # Invalid NaN / Inf samples
    bad_y = np.array([0.1, float("nan"), 0.2] * 20, dtype=np.float32)
    with pytest.raises(SpectrogramError):
        compute_spectrogram(bad_y, sr=sr)

    # Corrupt file on disk
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not a valid riff wav file but over 44 bytes long padding here")
    with pytest.raises(SpectrogramError):
        compute_spectrogram_from_file(corrupt)
