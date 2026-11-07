"""Acoustic feature extraction. Every feature is used by classification, behavior, or explanation."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from ..config import TARGET_SR


def extract_features(y: np.ndarray, sr: int = TARGET_SR) -> dict[str, Any]:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=-1)
    n = int(y.size)
    duration = float(n / sr) if sr else 0.0
    if n < int(0.05 * sr):
        return _empty_features(duration)

    hop = 512
    n_fft = 2048
    rms = librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=n_fft, hop_length=hop)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=n_fft, hop_length=hop)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=n_fft, hop_length=hop)[0]
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=n_fft, hop_length=hop)[0]
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_fft=n_fft, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=n_fft, hop_length=hop)
    mfcc_delta = librosa.feature.delta(mfcc) if mfcc.shape[1] >= 9 else np.zeros_like(mfcc)
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Focus spectral statistics on active (non-silent) vocalization frames so room silence does not dilute features
    rms_thresh = max(float(np.percentile(rms, 25)) * 1.35, float(np.max(rms)) * 0.10, 1e-4)
    active = rms >= rms_thresh
    if not np.any(active):
        active = np.ones_like(rms, dtype=bool)
    S_active = S[:, active]
    band_energy = _band_energy_ratios(S_active, freqs)
    dom_freq, tonality_idx, subharm_ratio = _spectral_shape_cues(S_active, freqs)
    am_roughness = _am_roughness(rms)

    # For long recordings (>12s), run expensive pitch/harmonic extraction on the most active 12s window
    max_pitch_samples = int(12.0 * sr)
    if n > max_pitch_samples:
        win_frames = max(1, int(12.0 * sr / hop))
        if rms.size > win_frames:
            csum = np.cumsum(np.insert(rms**2, 0, 0.0))
            best_f = int(np.argmax(csum[win_frames:] - csum[:-win_frames]))
            s_idx = best_f * hop
            y_pitch = y[s_idx : s_idx + max_pitch_samples]
        else:
            y_pitch = y[:max_pitch_samples]
        rms_pitch = librosa.feature.rms(y=y_pitch, frame_length=n_fft, hop_length=hop)[0]
        p_thresh = max(float(np.percentile(rms_pitch, 25)) * 1.35, float(np.max(rms_pitch)) * 0.10, 1e-4)
        active_pitch = rms_pitch >= p_thresh
    else:
        y_pitch = y
        active_pitch = active

    f0, voiced_flag, _ = librosa.pyin(
        y_pitch,
        fmin=60,
        fmax=3500,
        sr=sr,
        hop_length=hop,
        fill_na=np.nan,
    )
    f0_active = f0[active_pitch] if f0.size == active_pitch.size else f0
    voiced = f0_active[np.isfinite(f0_active)]
    if voiced.size == 0:
        voiced = f0[np.isfinite(f0)]
    voiced_ratio = float(np.mean(np.isfinite(f0_active))) if f0_active.size else 0.0
    f0_mean = float(np.nanmean(voiced)) if voiced.size else 0.0
    f0_std = float(np.nanstd(voiced)) if voiced.size else 0.0
    f0_min = float(np.nanmin(voiced)) if voiced.size else 0.0
    f0_max = float(np.nanmax(voiced)) if voiced.size else 0.0
    f0_range = f0_max - f0_min
    f0_cv = float(f0_std / (f0_mean + 1e-9)) if f0_mean else 0.0
    pitch_slope = float(np.polyfit(np.arange(voiced.size), voiced, 1)[0]) if voiced.size >= 3 else 0.0

    hnr = _hnr(y_pitch, sr, f0_mean if f0_mean else (dom_freq if 60 <= dom_freq <= 1500 else 150.0))
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")
    onset_times = np.asarray(onsets, dtype=float)
    onset_rate = float(onset_times.size / max(duration, 1e-6))
    ioi = np.diff(onset_times)
    pulse_cv = float(np.std(ioi) / (np.mean(ioi) + 1e-9)) if ioi.size >= 2 else 0.0
    pulse_regularity = float(1.0 / (1.0 + pulse_cv)) if ioi.size >= 2 else 0.0

    events = _energy_events(y, sr)
    event_count = len(events)
    event_durs = [e["duration"] for e in events]
    event_mean_dur = float(np.mean(event_durs)) if event_durs else duration
    event_max_dur = float(np.max(event_durs)) if event_durs else duration
    active_dur_ratio = float(sum(event_durs) / max(duration, 1e-6)) if event_durs else float(np.mean(active))

    harmonic = librosa.effects.harmonic(y_pitch, margin=2.0)
    harm_ratio = float(np.sum(harmonic**2) / (np.sum(y_pitch**2) + 1e-12))

    spectral_flux = _spectral_flux(S_active if S_active.shape[1] >= 2 else S)

    features = {
        "duration": duration,
        "rms": float(np.mean(rms[active])),
        "rms_std": float(np.std(rms)),
        "peak": float(np.max(np.abs(y))),
        "zcr_mean": float(np.mean(zcr[active])),
        "zcr_std": float(np.std(zcr[active])),
        "centroid_mean": float(np.mean(centroid[active])),
        "centroid_std": float(np.std(centroid[active])),
        "bandwidth_mean": float(np.mean(bandwidth[active])),
        "rolloff_mean": float(np.mean(rolloff[active])),
        "flatness_mean": float(np.mean(flatness[active])),
        "contrast_mean": float(np.mean(contrast[:, active])),
        "mfcc_mean": [float(x) for x in np.mean(mfcc[:, active], axis=1)],
        "mfcc_std": [float(x) for x in np.std(mfcc[:, active], axis=1)],
        "mfcc_delta_mean": [float(x) for x in np.mean(np.abs(mfcc_delta[:, active]), axis=1)],
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "f0_min": f0_min,
        "f0_max": f0_max,
        "f0_range": f0_range,
        "f0_cv": f0_cv,
        "pitch_slope": pitch_slope,
        "dominant_freq": dom_freq,
        "tonality_index": tonality_idx,
        "subharmonic_ratio": subharm_ratio,
        "am_roughness": am_roughness,
        "voiced_ratio": voiced_ratio,
        "hnr_db": hnr,
        "onset_rate": onset_rate,
        "onset_count": int(onset_times.size),
        "pulse_cv": pulse_cv,
        "pulse_regularity": pulse_regularity,
        "event_count": event_count,
        "event_mean_duration": event_mean_dur,
        "event_max_duration": event_max_dur,
        "active_duration_ratio": min(1.0, active_dur_ratio),
        "harmonic_ratio": harm_ratio,
        "spectral_flux": spectral_flux,
        "low_energy_ratio": band_energy["low"],
        "mid_energy_ratio": band_energy["mid"],
        "high_energy_ratio": band_energy["high"],
        "very_high_energy_ratio": band_energy["very_high"],
        "crest_factor": float(np.max(np.abs(y)) / (float(np.sqrt(np.mean(y**2))) + 1e-12)),
    }
    return features


def _spectral_shape_cues(S_active: np.ndarray, freqs: np.ndarray) -> tuple[float, float, float]:
    if S_active.size == 0:
        return 0.0, 0.0, 0.0
    power_profile = np.mean(S_active**2, axis=1)
    valid = (freqs >= 55) & (freqs <= 5500)
    if not np.any(valid):
        return 0.0, 0.0, 0.0
    p_valid = power_profile[valid]
    f_valid = freqs[valid]
    idx = int(np.argmax(p_valid))
    dom_freq = float(f_valid[idx])
    mean_p = float(np.mean(p_valid) + 1e-12)
    tonality_idx = float(np.max(p_valid) / mean_p)
    sub_mask = (freqs >= 55) & (freqs < 260)
    mid_mask = (freqs >= 260) & (freqs < 1200)
    sub_e = float(np.sum(power_profile[sub_mask]))
    mid_e = float(np.sum(power_profile[mid_mask]) + 1e-12)
    subharm_ratio = float(sub_e / (sub_e + mid_e + 1e-12))
    return dom_freq, tonality_idx, subharm_ratio


def _am_roughness(rms: np.ndarray) -> float:
    if rms.size < 6:
        return 0.0
    diff = np.abs(np.diff(rms))
    return float(np.mean(diff) / (float(np.mean(rms)) + 1e-9))


def _band_energy_ratios(S: np.ndarray, freqs: np.ndarray) -> dict[str, float]:
    power = S**2
    total = float(np.sum(power) + 1e-12)

    def _r(lo: float, hi: float) -> float:
        mask = (freqs >= lo) & (freqs < hi)
        return float(np.sum(power[mask, :]) / total)

    return {
        "low": _r(0, 400),
        "mid": _r(400, 2000),
        "high": _r(2000, 5000),
        "very_high": _r(5000, 11000),
    }


def _hnr(y: np.ndarray, sr: int, f0: float) -> float:
    """Active-frame harmonic-to-noise ratio via local peak autocorrelation in the vocal pitch band."""
    _ = f0
    if y.size < int(sr * 0.04):
        return 0.0
    frame = int(0.045 * sr)
    hop = max(1, frame // 2)
    min_lag = max(2, int(sr / 2600))
    max_lag = min(frame // 2, int(sr / 65))
    if min_lag >= max_lag:
        return 0.0
    frame_rms = []
    segs = []
    for i in range(0, max(1, y.size - frame), hop):
        seg = y[i : i + frame]
        r = float(np.sqrt(np.mean(seg**2)))
        frame_rms.append(r)
        segs.append(seg)
    if not segs:
        return 0.0
    rms_arr = np.asarray(frame_rms)
    thresh = max(float(np.percentile(rms_arr, 30)) * 1.3, float(np.max(rms_arr)) * 0.12, 1e-4)
    n_fft = 1 << (2 * frame - 1).bit_length()
    vals = []
    for seg, r in zip(segs, frame_rms):
        if r < thresh:
            continue
        seg = seg - float(np.mean(seg))
        ac0 = float(np.dot(seg, seg) + 1e-12)
        spec = np.fft.rfft(seg, n=n_fft)
        acf = np.fft.irfft(spec * np.conj(spec), n=n_fft)[: max_lag + 1]
        peak_ac = float(np.max(acf[min_lag : max_lag + 1]))
        ratio = min(max(peak_ac / ac0, 1e-4), 0.995)
        hnr = 10.0 * np.log10(ratio / (1.0 - ratio) + 1e-12)
        vals.append(float(hnr))
    return float(np.median(vals)) if vals else 0.0


def _spectral_flux(S: np.ndarray) -> float:
    if S.shape[1] < 2:
        return 0.0
    diff = np.diff(S, axis=1)
    flux = np.sqrt(np.sum(np.clip(diff, 0, None) ** 2, axis=0))
    return float(np.mean(flux))


def _energy_events(y: np.ndarray, sr: int, min_dur: float = 0.045) -> list[dict[str, float]]:
    frame = max(1, int(0.01 * sr))
    rms = np.sqrt(np.convolve(y**2, np.ones(frame) / frame, mode="same"))
    thresh = max(float(np.percentile(rms, 30)) * 1.55, float(np.max(rms)) * 0.11, 1e-4)
    mask = rms > thresh
    events: list[dict[str, float]] = []
    i = 0
    n = mask.size
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        dur = (j - i) / sr
        if dur >= min_dur:
            events.append({"start": i / sr, "end": j / sr, "duration": dur})
        i = j
    if not events and float(np.max(np.abs(y))) > 1e-3:
        events.append({"start": 0.0, "end": y.size / sr, "duration": y.size / sr})
    return events


def _empty_features(duration: float) -> dict[str, Any]:
    return {
        "duration": duration,
        "rms": 0.0,
        "rms_std": 0.0,
        "peak": 0.0,
        "zcr_mean": 0.0,
        "zcr_std": 0.0,
        "centroid_mean": 0.0,
        "centroid_std": 0.0,
        "bandwidth_mean": 0.0,
        "rolloff_mean": 0.0,
        "flatness_mean": 0.0,
        "contrast_mean": 0.0,
        "mfcc_mean": [0.0] * 13,
        "mfcc_std": [0.0] * 13,
        "mfcc_delta_mean": [0.0] * 13,
        "f0_mean": 0.0,
        "f0_std": 0.0,
        "f0_min": 0.0,
        "f0_max": 0.0,
        "f0_range": 0.0,
        "f0_cv": 0.0,
        "pitch_slope": 0.0,
        "dominant_freq": 0.0,
        "tonality_index": 0.0,
        "subharmonic_ratio": 0.0,
        "am_roughness": 0.0,
        "voiced_ratio": 0.0,
        "hnr_db": 0.0,
        "onset_rate": 0.0,
        "onset_count": 0,
        "pulse_cv": 0.0,
        "pulse_regularity": 0.0,
        "event_count": 0,
        "event_mean_duration": 0.0,
        "event_max_duration": 0.0,
        "active_duration_ratio": 0.0,
        "harmonic_ratio": 0.0,
        "spectral_flux": 0.0,
        "low_energy_ratio": 0.0,
        "mid_energy_ratio": 0.0,
        "high_energy_ratio": 0.0,
        "very_high_energy_ratio": 0.0,
        "crest_factor": 0.0,
    }


def feature_vector(features: dict[str, Any]) -> np.ndarray:
    """Numeric vector for supervised models. Order is stable."""
    keys = [
        "duration",
        "rms",
        "rms_std",
        "zcr_mean",
        "zcr_std",
        "centroid_mean",
        "centroid_std",
        "bandwidth_mean",
        "rolloff_mean",
        "flatness_mean",
        "contrast_mean",
        "f0_mean",
        "f0_std",
        "f0_range",
        "f0_cv",
        "pitch_slope",
        "dominant_freq",
        "tonality_index",
        "subharmonic_ratio",
        "am_roughness",
        "voiced_ratio",
        "hnr_db",
        "onset_rate",
        "pulse_regularity",
        "event_count",
        "event_mean_duration",
        "event_max_duration",
        "active_duration_ratio",
        "harmonic_ratio",
        "low_energy_ratio",
        "mid_energy_ratio",
        "high_energy_ratio",
        "very_high_energy_ratio",
        "crest_factor",
        "spectral_flux",
    ]
    base = [float(features.get(k, 0.0) or 0.0) for k in keys]
    mfcc_m = list(features.get("mfcc_mean") or [0.0] * 13)[:13]
    mfcc_s = list(features.get("mfcc_std") or [0.0] * 13)[:13]
    mfcc_d = list(features.get("mfcc_delta_mean") or [0.0] * 13)[:13]
    vec = np.asarray(base + mfcc_m + mfcc_s + mfcc_d, dtype=np.float32)
    return np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
