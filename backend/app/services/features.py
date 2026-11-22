"""Acoustic feature extraction. Every feature is used by classification, behavior, or explanation."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from ..config import DATA_DIR, TARGET_SR

_YAMNET_SESSION: Any = False  # False = not probed, None = unavailable
_CANINE_CORE_IDX = [69, 70, 71, 72, 73, 74, 75, 21, 34, 35, 40, 41, 117]
_YAMNET_SUBSET_IDX = [
    0, 1, 21, 22, 24, 34, 35, 38, 39, 40, 41, 42,
    67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79,
    81, 103, 104, 111, 112, 117, 355,
]
_CANINE_NORM_COLS = [69, 70, 71, 72, 73, 74, 75, 21, 34, 40]
YAMNET_FEATURE_DIM = len(_YAMNET_SUBSET_IDX) * 2 + len(_CANINE_NORM_COLS) * 2  # 84 dims


def _get_yamnet_session() -> Any:
    global _YAMNET_SESSION
    if _YAMNET_SESSION is not False:
        return _YAMNET_SESSION
    onnx_path = DATA_DIR / "models" / "pretrained" / "yamnet.onnx"
    if not onnx_path.exists():
        _YAMNET_SESSION = None
        return None
    try:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.enable_cpu_mem_arena = False
        opts.enable_mem_pattern = False
        _YAMNET_SESSION = ort.InferenceSession(
            str(onnx_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
    except Exception:
        _YAMNET_SESSION = None
    return _YAMNET_SESSION


def trim_active_window_16k(y: np.ndarray, sr: int) -> np.ndarray:
    """
    Active-bout onset/RMS window selector:
    Strips leading/trailing silence (top_db=24) and selects the highest-energy
    contiguous vocalization window (up to 6.0s), resampled to 16 kHz and
    zero-padded (never pulse-repeated) to >= 16,000 samples for YAMNet ONNX.
    """
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=-1)
    y = y - float(np.mean(y))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1e-4:
        y = y / peak * 0.95

    y_trim, _ = librosa.effects.trim(y, top_db=24, frame_length=1024, hop_length=256)
    if y_trim.size < int(0.10 * sr):
        y_trim = y

    max_len = int(6.0 * sr)
    if y_trim.size > max_len:
        hop = max(1, int(0.10 * sr))
        best_s = 0
        best_e = -1.0
        for s in range(0, y_trim.size - max_len + 1, hop):
            e = float(np.mean(y_trim[s : s + max_len] ** 2))
            if e > best_e:
                best_e = e
                best_s = s
        y_trim = y_trim[best_s : best_s + max_len]

    y16 = librosa.resample(y_trim, orig_sr=sr, target_sr=16000).astype(np.float32) if sr != 16000 else y_trim
    if y16.size < 16000:
        pad_total = 16000 - y16.size
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        y16 = np.pad(y16, (pad_left, pad_right), mode="constant")
    return y16


def extract_yamnet_summary(y: np.ndarray, sr: int) -> list[float]:
    """Run pretrained AudioSet YAMNet ONNX over the active vocalization bout and pool 84 domain scores."""
    sess = _get_yamnet_session()
    if sess is None or y.size == 0:
        return [0.0] * YAMNET_FEATURE_DIM
    try:
        y16 = trim_active_window_16k(y, sr)
        scores, _, _ = sess.run(None, {"waveform": y16})
        sal = np.max(scores[:, _CANINE_CORE_IDX], axis=1) + 0.1 * np.max(scores, axis=1) + 1e-4
        w = sal / np.sum(sal)
        sc_wm = np.sum(scores * w[:, None], axis=0)
        sc_mx = np.max(scores, axis=0)

        sub_wm = sc_wm[_YAMNET_SUBSET_IDX]
        sub_mx = sc_mx[_YAMNET_SUBSET_IDX]
        c_wm = sc_wm[_CANINE_NORM_COLS]
        c_mx = sc_mx[_CANINE_NORM_COLS]
        c_norm_wm = c_wm / (float(np.sum(c_wm)) + 1e-6)
        c_norm_mx = c_mx / (float(np.sum(c_mx)) + 1e-6)
        out = np.concatenate([sub_wm, sub_mx, c_norm_wm, c_norm_mx])
        return [float(x) for x in np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)]
    except Exception:
        return [0.0] * YAMNET_FEATURE_DIM


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
    if mfcc.shape[1] >= 9:
        mfcc_delta = librosa.feature.delta(mfcc)
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
    elif mfcc.shape[1] >= 3:
        mfcc_delta = np.gradient(mfcc, axis=1)
        mfcc_delta2 = np.gradient(mfcc_delta, axis=1)
    else:
        mfcc_delta = np.zeros_like(mfcc)
        mfcc_delta2 = np.zeros_like(mfcc)
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

    # 16-band log-mel statistics computed directly from active STFT power spectrum
    mel_spec = librosa.feature.melspectrogram(S=S_active**2, sr=sr, n_fft=n_fft, hop_length=hop, n_mels=16, fmin=50.0, fmax=min(8000.0, sr / 2.0))
    log_mel = librosa.power_to_db(mel_spec + 1e-10, ref=np.max)
    log_mel_mean = [float(x) for x in np.mean(log_mel, axis=1)]
    log_mel_std = [float(x) for x in np.std(log_mel, axis=1)]

    rolloff_low = librosa.feature.spectral_rolloff(S=S_active, sr=sr, roll_percent=0.25)[0]
    rms_act = rms[active]
    rms_p10, rms_p50, rms_p90 = [float(x) for x in np.percentile(rms_act, [10, 50, 90])] if rms_act.size else (0.0, 0.0, 0.0)
    rms_diff = np.diff(rms) if rms.size >= 2 else np.zeros(1, dtype=np.float32)
    attack_slope_max = float(np.max(rms_diff)) if rms_diff.size else 0.0
    decay_slope_min = float(np.min(rms_diff)) if rms_diff.size else 0.0
    centroid_act = centroid[active]
    centroid_p10, centroid_p50, centroid_p90 = [float(x) for x in np.percentile(centroid_act, [10, 50, 90])] if centroid_act.size else (0.0, 0.0, 0.0)

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
    if voiced.size >= 2:
        f0_p10, f0_p50, f0_p90 = [float(x) for x in np.percentile(voiced, [10, 50, 90])]
        f0_iqr = float(np.percentile(voiced, 75) - np.percentile(voiced, 25))
        f0_jitter = float(np.mean(np.abs(np.diff(voiced))) / (f0_mean + 1e-9))
    elif voiced.size == 1:
        f0_p10 = f0_p50 = f0_p90 = float(voiced[0])
        f0_iqr = 0.0
        f0_jitter = 0.0
    else:
        f0_p10 = f0_p50 = f0_p90 = f0_iqr = f0_jitter = 0.0

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
        "contrast_std": float(np.std(contrast[:, active])),
        "contrast_bands_mean": [float(x) for x in np.mean(contrast[:, active], axis=1)],
        "contrast_bands_std": [float(x) for x in np.std(contrast[:, active], axis=1)],
        "bandwidth_std": float(np.std(bandwidth[active])),
        "rolloff_std": float(np.std(rolloff[active])),
        "rolloff_low_mean": float(np.mean(rolloff_low)) if rolloff_low.size else 0.0,
        "flatness_std": float(np.std(flatness[active])),
        "centroid_p10": centroid_p10,
        "centroid_p50": centroid_p50,
        "centroid_p90": centroid_p90,
        "rms_p10": rms_p10,
        "rms_p50": rms_p50,
        "rms_p90": rms_p90,
        "rms_dynamic_range": float(rms_p90 - rms_p10),
        "attack_slope_max": attack_slope_max,
        "decay_slope_min": decay_slope_min,
        "mfcc_mean": [float(x) for x in np.mean(mfcc[:, active], axis=1)],
        "mfcc_std": [float(x) for x in np.std(mfcc[:, active], axis=1)],
        "mfcc_p10": [float(x) for x in np.percentile(mfcc[:, active], 10, axis=1)],
        "mfcc_p90": [float(x) for x in np.percentile(mfcc[:, active], 90, axis=1)],
        "mfcc_delta_mean": [float(x) for x in np.mean(np.abs(mfcc_delta[:, active]), axis=1)],
        "mfcc_delta_std": [float(x) for x in np.std(mfcc_delta[:, active], axis=1)],
        "mfcc_delta2_mean": [float(x) for x in np.mean(np.abs(mfcc_delta2[:, active]), axis=1)],
        "mfcc_delta2_std": [float(x) for x in np.std(mfcc_delta2[:, active], axis=1)],
        "log_mel_mean": log_mel_mean,
        "log_mel_std": log_mel_std,
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "f0_min": f0_min,
        "f0_max": f0_max,
        "f0_range": f0_range,
        "f0_cv": f0_cv,
        "f0_p10": f0_p10,
        "f0_p50": f0_p50,
        "f0_p90": f0_p90,
        "f0_iqr": f0_iqr,
        "f0_jitter": f0_jitter,
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
        "yamnet_summary": extract_yamnet_summary(y, sr),
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
        "contrast_std": 0.0,
        "contrast_bands_mean": [0.0] * 7,
        "contrast_bands_std": [0.0] * 7,
        "bandwidth_std": 0.0,
        "rolloff_std": 0.0,
        "rolloff_low_mean": 0.0,
        "flatness_std": 0.0,
        "centroid_p10": 0.0,
        "centroid_p50": 0.0,
        "centroid_p90": 0.0,
        "rms_p10": 0.0,
        "rms_p50": 0.0,
        "rms_p90": 0.0,
        "rms_dynamic_range": 0.0,
        "attack_slope_max": 0.0,
        "decay_slope_min": 0.0,
        "mfcc_mean": [0.0] * 13,
        "mfcc_std": [0.0] * 13,
        "mfcc_p10": [0.0] * 13,
        "mfcc_p90": [0.0] * 13,
        "mfcc_delta_mean": [0.0] * 13,
        "mfcc_delta_std": [0.0] * 13,
        "mfcc_delta2_mean": [0.0] * 13,
        "mfcc_delta2_std": [0.0] * 13,
        "log_mel_mean": [0.0] * 16,
        "log_mel_std": [0.0] * 16,
        "f0_mean": 0.0,
        "f0_std": 0.0,
        "f0_min": 0.0,
        "f0_max": 0.0,
        "f0_range": 0.0,
        "f0_cv": 0.0,
        "f0_p10": 0.0,
        "f0_p50": 0.0,
        "f0_p90": 0.0,
        "f0_iqr": 0.0,
        "f0_jitter": 0.0,
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
        "yamnet_summary": [0.0] * YAMNET_FEATURE_DIM,
    }


def feature_vector(features: dict[str, Any]) -> np.ndarray:
    """Numeric vector for supervised models. Order is stable (v2 enhanced acoustic schema)."""
    from .classifier import CLASSES, _class_scores, _softmax

    keys = [
        "duration",
        "rms",
        "rms_std",
        "rms_p10",
        "rms_p50",
        "rms_p90",
        "rms_dynamic_range",
        "attack_slope_max",
        "decay_slope_min",
        "peak",
        "zcr_mean",
        "zcr_std",
        "centroid_mean",
        "centroid_std",
        "centroid_p10",
        "centroid_p50",
        "centroid_p90",
        "bandwidth_mean",
        "bandwidth_std",
        "rolloff_mean",
        "rolloff_std",
        "rolloff_low_mean",
        "flatness_mean",
        "flatness_std",
        "contrast_mean",
        "contrast_std",
        "f0_mean",
        "f0_std",
        "f0_min",
        "f0_max",
        "f0_range",
        "f0_cv",
        "f0_p10",
        "f0_p50",
        "f0_p90",
        "f0_iqr",
        "f0_jitter",
        "pitch_slope",
        "dominant_freq",
        "tonality_index",
        "subharmonic_ratio",
        "am_roughness",
        "voiced_ratio",
        "hnr_db",
        "onset_rate",
        "onset_count",
        "pulse_cv",
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

    def _fixed_list(key: str, length: int) -> list[float]:
        raw = list(features.get(key) or [])
        if len(raw) < length:
            raw.extend([0.0] * (length - len(raw)))
        return [float(x or 0.0) for x in raw[:length]]

    mfcc_m = _fixed_list("mfcc_mean", 13)
    mfcc_s = _fixed_list("mfcc_std", 13)
    mfcc_p10 = _fixed_list("mfcc_p10", 13)
    mfcc_p90 = _fixed_list("mfcc_p90", 13)
    mfcc_dm = _fixed_list("mfcc_delta_mean", 13)
    mfcc_ds = _fixed_list("mfcc_delta_std", 13)
    mfcc_d2m = _fixed_list("mfcc_delta2_mean", 13)
    mfcc_d2s = _fixed_list("mfcc_delta2_std", 13)
    mel_m = _fixed_list("log_mel_mean", 16)
    mel_s = _fixed_list("log_mel_std", 16)
    cb_m = _fixed_list("contrast_bands_mean", 7)
    cb_s = _fixed_list("contrast_bands_std", 7)
    yam_s = _fixed_list("yamnet_summary", YAMNET_FEATURE_DIM)

    heur_raw = _class_scores(features)
    heur_probs = _softmax(heur_raw)
    priors = [float(heur_raw.get(c, 0.0)) for c in CLASSES] + [float(heur_probs.get(c, 0.0)) for c in CLASSES]

    vec = np.asarray(
        base
        + mfcc_m
        + mfcc_s
        + mfcc_p10
        + mfcc_p90
        + mfcc_dm
        + mfcc_ds
        + mfcc_d2m
        + mfcc_d2s
        + mel_m
        + mel_s
        + cb_m
        + cb_s
        + priors
        + yam_s,
        dtype=np.float32,
    )
    return np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
