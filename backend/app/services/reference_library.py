"""
Genuine Dog Audio Reference Library & Bioacoustic Analysis Pipeline (Engine B Foundation).

Preserves every original recording unchanged, computes SHA-256 and technical validation,
separates automatic category suggestions from human-confirmed annotations, and extracts
time-domain, frequency-domain, time-frequency, and vocalization-specific profiles.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf

from ..config import ROOT, TARGET_SR
from .audio import _decode_any, assess_quality, preprocess, sniff_format

REPO_DATA_DIR = ROOT / "data"
# Tests (and sandboxes) point this at a throw-away copy so they can never mutate the real library.
REFERENCE_DIR = Path(os.getenv("CANINESENSE_REFERENCE_DIR", str(REPO_DATA_DIR / "reference_library"))).resolve()
REF_RAW_DIR = REFERENCE_DIR / "raw"
REF_PROC_DIR = REFERENCE_DIR / "processed"
REF_PLOTS_DIR = REFERENCE_DIR / "plots"
REF_MANIFEST_JSON = REFERENCE_DIR / "manifest.json"
REF_MANIFEST_CSV = REFERENCE_DIR / "manifest.csv"

SUPPORTED_REFERENCE_CATEGORIES: tuple[str, ...] = (
    "BARK",
    "GROWL",
    "HOWL",
    "WHINE",
    "YIP",
    "YELP",
    "WHIMPER",
    "CRY",
    "GRUNT",
    "GROAN",
    "PANT",
    "MIXED",
    "UNKNOWN",
)

# Bidirectional mapping between Engine B profile identifiers and canonical reference categories
PROFILE_TO_CATEGORY: dict[str, str] = {
    "bark": "BARK",
    "growl": "GROWL",
    "howl": "HOWL",
    "whine": "WHINE",
    "yip": "YIP",
    "yelp": "YELP",
    "whimper": "WHIMPER",
    "cry": "CRY",
    "grunt": "GRUNT",
    "groan": "GROAN",
    "pant": "PANT",
    "mixed": "MIXED",
    "soft_attention": "WHIMPER",
}

CATEGORY_FALLBACK_ORDER: dict[str, list[str]] = {
    "BARK": ["BARK", "MIXED", "YIP"],
    "GROWL": ["GROWL", "GRUNT", "GROAN", "MIXED"],
    "HOWL": ["HOWL", "CRY", "GROAN", "WHINE"],
    "WHINE": ["WHINE", "WHIMPER", "CRY", "YIP"],
    "YIP": ["YIP", "YELP", "BARK"],
    "YELP": ["YELP", "YIP", "CRY", "BARK"],
    "WHIMPER": ["WHIMPER", "WHINE", "CRY"],
    "CRY": ["CRY", "WHIMPER", "WHINE", "HOWL"],
    "GRUNT": ["GRUNT", "GROAN", "GROWL", "BARK"],
    "GROAN": ["GROAN", "GRUNT", "GROWL", "HOWL"],
    "PANT": ["PANT", "GRUNT"],
    "MIXED": ["MIXED", "BARK", "GROWL", "WHINE"],
    "UNKNOWN": ["BARK", "WHINE", "HOWL", "YIP"],
}

_MANIFEST_CACHE: dict[str, Any] | None = None
_MANIFEST_WRITE_LOCK = threading.RLock()


def _normalize_asset_paths(asset: dict[str, Any]) -> dict[str, Any]:
    """Dynamically rebind stored asset paths to the current runtime directories.
    Ensures cross-platform portability when assets were pre-indexed on Windows or Linux.
    """
    mappings = [
        ("processed_path", REF_PROC_DIR),
        ("spectrogram_path", REF_PLOTS_DIR),
        ("waveform_path", REF_PLOTS_DIR),
        ("raw_path", REF_RAW_DIR),
    ]
    for key, target_dir in mappings:
        val = asset.get(key)
        if val:
            p = Path(val)
            if not p.exists():
                candidate = target_dir / p.name
                if candidate.exists():
                    asset[key] = str(candidate)
    return asset


def normalize_category(cat: str | None) -> str:
    if not cat:
        return "BARK"
    raw = cat.strip()
    low = raw.lower()
    if low in PROFILE_TO_CATEGORY:
        return PROFILE_TO_CATEGORY[low]
    up = raw.upper()
    if up in SUPPORTED_REFERENCE_CATEGORIES:
        return up
    return "UNKNOWN"


def category_to_legacy_profile(cat: str | None) -> str:
    if cat and cat.strip().lower() == "soft_attention":
        return "soft_attention"
    up = normalize_category(cat)
    mapping = {
        "BARK": "bark",
        "GROWL": "growl",
        "HOWL": "howl",
        "WHINE": "whine",
        "YIP": "yip",
        "YELP": "yelp",
        "WHIMPER": "whimper",
        "CRY": "cry",
        "GRUNT": "grunt",
        "GROAN": "groan",
        "PANT": "pant",
        "MIXED": "bark",
        "UNKNOWN": "bark",
    }
    return mapping.get(up, "bark")


def compute_reference_acoustic_profile(y: np.ndarray, sr: int = TARGET_SR) -> dict[str, Any]:
    """
    Extract comprehensive time-domain, frequency-domain, time-frequency, and
    vocalization-specific bioacoustic characteristics without inventing biological claims.
    """
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=-1)
    n = int(y.size)
    duration = float(n / sr) if sr > 0 else 0.0
    if n < int(0.04 * sr) or not np.all(np.isfinite(y)):
        return {"valid": False, "duration_sec": round(duration, 4)}

    hop = 256
    n_fft = min(1024, max(256, 1 << int(np.floor(np.log2(max(256, n))))))
    if hop >= n_fft:
        hop = n_fft // 4

    rms_frames = librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop)[0]
    peak = float(np.max(np.abs(y)))
    rms_overall = float(np.sqrt(np.mean(y**2)))
    crest_factor = float(peak / (rms_overall + 1e-12))
    clipping_ratio = float(np.mean(np.abs(y) > 0.99))

    # Active frame mask
    rms_thresh = max(float(np.percentile(rms_frames, 20)) * 1.3, float(np.max(rms_frames)) * 0.10, 1e-4)
    active = rms_frames >= rms_thresh
    if not np.any(active):
        active = np.ones_like(rms_frames, dtype=bool)
    silence_ratio = float(1.0 - np.mean(active))

    # 24-point normalized amplitude envelope summary
    env_points = 24
    if rms_frames.size >= env_points:
        idx_grid = np.linspace(0, rms_frames.size - 1, env_points)
        env_contour = np.interp(idx_grid, np.arange(rms_frames.size), rms_frames)
    else:
        env_contour = rms_frames
    max_env = float(np.max(env_contour)) + 1e-12
    env_norm = [round(float(v / max_env), 4) for v in env_contour]

    # Attack and decay times on primary event
    peak_frame = int(np.argmax(rms_frames))
    frame_dt = hop / float(sr)
    pre_frames = rms_frames[: peak_frame + 1]
    onset_candidates = np.where(pre_frames <= 0.15 * float(rms_frames[peak_frame]))[0]
    onset_frame = int(onset_candidates[-1]) if onset_candidates.size else 0
    attack_time_sec = max(frame_dt, (peak_frame - onset_frame) * frame_dt)

    post_frames = rms_frames[peak_frame:]
    release_candidates = np.where(post_frames <= 0.20 * float(rms_frames[peak_frame]))[0]
    decay_frames = int(release_candidates[0]) if release_candidates.size else len(post_frames) - 1
    decay_time_sec = max(frame_dt, decay_frames * frame_dt)

    # Energy events segmentation
    events: list[dict[str, float]] = []
    in_ev = False
    ev_start = 0
    for i, is_act in enumerate(active):
        if is_act and not in_ev:
            in_ev = True
            ev_start = i
        elif not is_act and in_ev:
            in_ev = False
            dur_ev = (i - ev_start) * frame_dt
            if dur_ev >= 0.04:
                events.append({"start_sec": round(ev_start * frame_dt, 3), "end_sec": round(i * frame_dt, 3), "duration_sec": round(dur_ev, 3)})
    if in_ev:
        dur_ev = (len(active) - ev_start) * frame_dt
        if dur_ev >= 0.04:
            events.append({"start_sec": round(ev_start * frame_dt, 3), "end_sec": round(len(active) * frame_dt, 3), "duration_sec": round(dur_ev, 3)})

    event_durs = [e["duration_sec"] for e in events]
    inter_event_intervals = [
        round(events[k + 1]["start_sec"] - events[k]["end_sec"], 3)
        for k in range(len(events) - 1)
        if events[k + 1]["start_sec"] > events[k]["end_sec"]
    ]

    # STFT & Spectral measurements on active frames
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    S_act = S[:, active] if S.shape[1] == active.size and np.any(active) else S

    centroid = librosa.feature.spectral_centroid(S=S_act, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S_act, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(S=S_act, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(S=S_act)[0]

    # Spectral flux
    if S_act.shape[1] >= 2:
        S_norm = S_act / (np.sum(S_act, axis=0, keepdims=True) + 1e-12)
        flux = float(np.mean(np.sqrt(np.sum(np.diff(S_norm, axis=1) ** 2, axis=0))))
    else:
        flux = 0.0

    # Band energy ratios
    power = S_act**2
    tot_pow = float(np.sum(power)) + 1e-12
    low_ratio = float(np.sum(power[(freqs >= 50) & (freqs < 400), :]) / tot_pow)
    mid_ratio = float(np.sum(power[(freqs >= 400) & (freqs < 2000), :]) / tot_pow)
    high_ratio = float(np.sum(power[(freqs >= 2000) & (freqs < 5000), :]) / tot_pow)
    vhigh_ratio = float(np.sum(power[freqs >= 5000, :]) / tot_pow)

    # Dominant frequency & subharmonic ratio
    mean_pow = np.mean(power, axis=1)
    valid_f = (freqs >= 60) & (freqs <= 5000)
    if np.any(valid_f):
        f_sub = freqs[valid_f]
        p_sub = mean_pow[valid_f]
        dom_freq = float(f_sub[int(np.argmax(p_sub))])
    else:
        dom_freq = 0.0

    sub_band = float(np.sum(mean_pow[(freqs >= 55) & (freqs < 250)]))
    mid_band = float(np.sum(mean_pow[(freqs >= 250) & (freqs < 1200)])) + 1e-12
    subharmonic_ratio = float(sub_band / (sub_band + mid_band))

    # Mel spectrogram & MFCC summary
    mel_spec = librosa.feature.melspectrogram(S=S_act**2, sr=sr, n_mels=16)
    mel_db = librosa.power_to_db(np.mean(mel_spec, axis=1) + 1e-12, ref=1.0)
    mfcc = librosa.feature.mfcc(S=librosa.power_to_db(mel_spec + 1e-12), n_mfcc=13)
    mfcc_mean = [round(float(v), 3) for v in np.mean(mfcc, axis=1)]

    # Pitch (F0) on up to 6s most active window using YIN + harmonicity/energy voicing gate
    max_win = int(6.0 * sr)
    if n > max_win:
        win_frames = max(1, int(6.0 * sr / hop))
        csum = np.cumsum(np.insert(rms_frames**2, 0, 0.0))
        best_f = int(np.argmax(csum[win_frames:] - csum[:-win_frames])) if rms_frames.size > win_frames else 0
        s_idx = best_f * hop
        y_focus = y[s_idx : s_idx + max_win]
    else:
        y_focus = y

    hop_f0 = max(256, hop * 2)
    win_f0 = min(1024, max(256, 1 << int(np.floor(np.log2(max(256, y_focus.size))))))
    if hop_f0 >= win_f0:
        hop_f0 = max(64, win_f0 // 2)
    try:
        yin_f0 = librosa.yin(y_focus, fmin=65, fmax=2600, sr=sr, frame_length=win_f0, hop_length=hop_f0)
        rms_f0 = librosa.feature.rms(y=y_focus, frame_length=win_f0, hop_length=hop_f0)[0]
        flat_f0 = librosa.feature.spectral_flatness(y=y_focus, n_fft=win_f0, hop_length=hop_f0)[0]
        min_len = min(yin_f0.size, rms_f0.size, flat_f0.size)
        yin_f0 = yin_f0[:min_len]
        rms_f0 = rms_f0[:min_len]
        flat_f0 = flat_f0[:min_len]
        voiced_mask = (
            np.isfinite(yin_f0)
            & (yin_f0 >= 68.0)
            & (yin_f0 <= 2500.0)
            & (rms_f0 >= max(1e-4, 0.16 * float(np.max(rms_f0))))
            & (flat_f0 <= 0.22)
        )
        voiced = yin_f0[voiced_mask]
        total_f0_frames = max(1, min_len)
    except Exception:
        voiced = np.zeros(0, dtype=np.float32)
        total_f0_frames = 1

    voiced_ratio = float(voiced.size / total_f0_frames)
    # Do not present unreliable pitch estimates as verified measurements
    f0_measurable = bool(voiced.size >= 3 and voiced_ratio >= 0.12)
    if f0_measurable:
        f0_mean: float | None = round(float(np.mean(voiced)), 2)
        f0_std: float | None = round(float(np.std(voiced)), 2)
        f0_min: float | None = round(float(np.min(voiced)), 2)
        f0_max: float | None = round(float(np.max(voiced)), 2)
        t_voiced = np.arange(voiced.size, dtype=float) * (hop_f0 / float(sr))
        pitch_slope: float | None = round(float(np.polyfit(t_voiced, voiced, 1)[0]), 2) if voiced.size >= 4 else 0.0
        traj_pts = min(16, voiced.size)
        traj_idx = np.linspace(0, voiced.size - 1, traj_pts).astype(int)
        f0_traj = [round(float(voiced[i]), 1) for i in traj_idx]
    else:
        f0_mean = None
        f0_std = None
        f0_min = None
        f0_max = None
        pitch_slope = None
        f0_traj = []

    # Harmonic-to-noise ratio (autocorrelation peak in vocal lag band)
    hnr_db = _estimate_hnr_db(y_focus, sr)
    am_roughness = float(np.mean(np.abs(np.diff(rms_frames))) / (float(np.mean(rms_frames)) + 1e-9)) if rms_frames.size >= 4 else 0.0

    # Vocalization-specific acoustic indices
    cent_mean = float(np.mean(centroid))
    flat_mean = float(np.mean(flatness))
    ev_mean_dur = float(np.mean(event_durs)) if event_durs else duration

    bark_impulsiveness = round(float(min(1.0, (crest_factor / 8.0) * (1.0 / max(0.08, attack_time_sec * 12.0)))), 3)
    growl_roughness = round(float(min(1.0, (low_ratio * 1.8 + subharmonic_ratio * 1.2) * (0.5 + am_roughness))), 3)
    howl_tonality = round(float(min(1.0, max(0.0, (hnr_db + 2.0) / 16.0) * min(1.0, ev_mean_dur / 0.8))), 3)
    whine_modulation = round(float(min(1.0, (1.0 if (f0_mean or dom_freq) > 520 else 0.3) * max(0.1, (hnr_db + 2.0) / 14.0))), 3)
    yip_compactness = round(float(min(1.0, (1.0 if ev_mean_dur < 0.28 else 0.3) * (1.0 if cent_mean > 1400 else 0.4))), 3)
    whimper_wavering = round(float(min(1.0, (0.8 if len(events) >= 2 else 0.3) * am_roughness * (1.0 if cent_mean > 1100 else 0.4))), 3)

    return {
        "valid": True,
        "time_domain": {
            "duration_sec": round(duration, 4),
            "rms_energy": round(rms_overall, 5),
            "peak_amplitude": round(peak, 5),
            "crest_factor": round(crest_factor, 3),
            "attack_time_sec": round(attack_time_sec, 4),
            "decay_time_sec": round(decay_time_sec, 4),
            "event_count": len(events),
            "event_mean_duration_sec": round(ev_mean_dur, 4),
            "event_max_duration_sec": round(float(max(event_durs)) if event_durs else duration, 4),
            "inter_event_interval_mean_sec": round(float(np.mean(inter_event_intervals)), 4) if inter_event_intervals else 0.0,
            "repetition_rate_hz": round(float(len(events) / max(duration, 0.1)), 3),
            "amplitude_envelope": env_norm,
            "clipping_ratio": round(clipping_ratio, 6),
            "silence_ratio": round(silence_ratio, 4),
        },
        "frequency_domain": {
            "f0_measurable": f0_measurable,
            "f0_mean_hz": f0_mean,
            "f0_std_hz": f0_std,
            "f0_min_hz": f0_min,
            "f0_max_hz": f0_max,
            "voiced_ratio": round(voiced_ratio, 3),
            "dominant_freq_hz": round(dom_freq, 1),
            "hnr_db": round(hnr_db, 2),
            "subharmonic_ratio": round(subharmonic_ratio, 4),
            "spectral_centroid_hz": round(cent_mean, 1),
            "spectral_bandwidth_hz": round(float(np.mean(bandwidth)), 1),
            "spectral_rolloff_hz": round(float(np.mean(rolloff)), 1),
            "spectral_flatness": round(flat_mean, 5),
            "spectral_flux": round(flux, 5),
            "band_energy_distribution": {
                "low_50_400_hz": round(low_ratio, 4),
                "mid_400_2000_hz": round(mid_ratio, 4),
                "high_2000_5000_hz": round(high_ratio, 4),
                "very_high_5000_11025_hz": round(vhigh_ratio, 4),
            },
        },
        "time_frequency": {
            "stft_n_fft": n_fft,
            "stft_hop_length": hop,
            "freq_resolution_hz": round(float(sr / n_fft), 2),
            "mfcc_mean": mfcc_mean,
            "mel_band_db": [round(float(v), 2) for v in mel_db],
            "f0_trajectory_hz": f0_traj,
            "pitch_slope_hz_per_sec": pitch_slope,
            "am_roughness": round(am_roughness, 4),
        },
        "vocalization_character": {
            "bark_impulsiveness": bark_impulsiveness,
            "growl_roughness_index": growl_roughness,
            "howl_sustained_tonality": howl_tonality,
            "whine_modulation_index": whine_modulation,
            "yip_transient_compactness": yip_compactness,
            "whimper_wavering_index": whimper_wavering,
        },
    }


def _estimate_hnr_db(y: np.ndarray, sr: int) -> float:
    if y.size < int(sr * 0.04):
        return 0.0
    frame = int(0.04 * sr)
    hop = max(1, frame // 2)
    min_lag = max(2, int(sr / 2500))
    max_lag = min(frame // 2, int(sr / 65))
    if min_lag >= max_lag:
        return 0.0
    hnrs: list[float] = []
    n_fft = 1 << (2 * frame - 1).bit_length()
    win = np.hanning(frame)
    for i in range(0, max(1, y.size - frame), hop):
        seg = y[i : i + frame]
        if float(np.sqrt(np.mean(seg**2))) < 0.01:
            continue
        wseg = (seg - np.mean(seg)) * win
        spec = np.fft.rfft(wseg, n=n_fft)
        ac = np.fft.irfft(spec * np.conj(spec), n=n_fft)[:frame]
        if ac[0] <= 1e-12:
            continue
        ac = ac / ac[0]
        r_max = float(np.clip(np.max(ac[min_lag:max_lag]), 1e-4, 0.995))
        hnrs.append(float(10.0 * np.log10(r_max / (1.0 - r_max))))
    return float(np.median(hnrs)) if hnrs else 0.0


def suggest_vocalization_category(
    filename: str,
    profile: dict[str, Any],
    manifest_hint: str | None = None,
) -> tuple[str, str]:
    """
    Return (suggested_category, confidence_note).
    Does not force uncertain recordings into a class; uses UNKNOWN when ambiguous.
    """
    low_name = filename.lower()
    if any(k in low_name for k in ("toymech", "squeaker", "couinement jouet", "pouet", "water fountain")):
        return "UNKNOWN", "Non-canine mechanical/ambient source filename"

    td = profile.get("time_domain", {})
    fd = profile.get("frequency_domain", {})
    bands = fd.get("band_energy_distribution", {})
    f0 = fd.get("f0_mean_hz") or fd.get("dominant_freq_hz") or 0.0
    dom = fd.get("dominant_freq_hz") or 0.0
    cent = fd.get("spectral_centroid_hz") or 0.0
    hnr = fd.get("hnr_db") or 0.0
    low_r = bands.get("low_50_400_hz") or 0.0
    high_r = bands.get("high_2000_5000_hz") or 0.0
    sub_r = fd.get("subharmonic_ratio") or 0.0
    ev_dur = td.get("event_mean_duration_sec") or td.get("duration_sec") or 0.5
    dur = td.get("duration_sec") or 0.5

    if "breathing" in low_name or "pant" in low_name:
        return "PANT", "Unvoiced/low-HNR rhythmic respiratory airflow pattern"

    if manifest_hint:
        mh = manifest_hint.strip().upper()
        if mh in SUPPORTED_REFERENCE_CATEGORIES and mh != "OTHER":
            return mh, "Curated acoustic audit label"

    if "singing" in low_name or "howl" in low_name:
        if low_r > 0.65 and dom < 280 and dur <= 1.5:
            return "GROAN", "Low-dominant sustained vocal onset"
        return "HOWL", "Sustained harmonic vocalization"

    if "crying" in low_name:
        if dur > 8.0:
            return "MIXED", "Multi-event recording containing both barks and high-pitched crying/whimpering"
        if f0 > 550 or cent > 1450:
            return "CRY", "High-pitched distress/crying vocalization segment"
        return "WHIMPER", "Plaintive wavering vocalization segment"

    if "growl" in low_name:
        if dur > 10.0:
            return "MIXED", "Multi-event recording containing both barks and low growls"
        if low_r >= 0.20 or dom < 350 or sub_r >= 0.14:
            return "GROWL", "Low-frequency rough/subharmonic vocalization"
        return "BARK", "Bark pulse within growl session"

    # Purely acoustic rules for field recordings (e.g., WhatsApp mpeg / mp3)
    if (f0 > 0 and f0 <= 185 and sub_r >= 0.12) or (dom <= 190 and low_r >= 0.12):
        if dur <= 1.5 or ev_dur <= 0.45:
            return "GRUNT", "Short low-frequency vocal pulse with subharmonic energy"
        return "GROWL", "Low-frequency vocalization with subharmonic roughness"

    if low_r >= 0.22 and sub_r >= 0.15:
        if hnr >= 6.0:
            return "GROAN", "Low-frequency tonal groan with high low-band energy"
        return "GROWL", "Low-frequency rough growl"

    if hnr >= 8.0 and ev_dur >= 0.45 and 240 <= (f0 or dom) <= 620:
        return "HOWL", "High-HNR sustained harmonic contour"

    if hnr >= 8.0 and (f0 >= 620 or cent >= 2200):
        if td.get("event_count", 1) >= 4:
            return "WHIMPER", "Repeated high-frequency tonal whimpering pulses"
        return "WHINE", "High-frequency tonal contour"

    if (f0 >= 1150 or dom >= 1350) and cent >= 1800:
        if ev_dur <= 0.25:
            return "YIP", "Short high-pitched impulsive vocalization"
        return "YELP", "High-pitched sharp yelp vocalization"

    if "spitz" in low_name or (f0 >= 900 and ev_dur <= 0.30):
        return "YIP", "High-pitched small-dog yip/bark burst"

    if 250 <= (f0 or dom) <= 1150 and cent >= 650:
        return "BARK", "Impulsive mid-band canine bark vocalization"

    return "UNKNOWN", "Acoustic profile did not match a single confidence threshold"


def _extract_focal_subclips(
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Extract targeted, clean vocalization sub-windows from multi-vocalization source files
    (e.g., ID 1060/1061 growl & grunt windows, ID 1544-1546 crying & whimpering windows,
    ID 2451 groan onset, ID 1547 panting window, ID 2352 old dog low grunt/bark) so every
    supported category has genuine reference audio coverage.
    """
    by_name: dict[str, Path] = {}
    for r in manifest_rows:
        if "segment_of=" not in (r.get("notes") or ""):
            p = Path(r["path"])
            if p.exists():
                by_name[r["source_filename"]] = p

    specs = [
        # (source_substr, start_sec, end_sec, category, confirmed, suffix_label, notes)
        ("ID 1060", 13.00, 14.50, "GROWL", "GROWL", "growl_deep_rumble", "Deep low-frequency canine growl (107.7 Hz dominant) from ID 1060"),
        ("ID 1060", 4.15, 5.45, "GROWL", "GROWL", "growl_bark_phrase", "Growl-bark vocalization phrase from ID 1060"),
        ("ID 1544", 3.10, 4.15, "CRY", "CRY", "crying_phrase_1", "High-pitched canine crying phrase from ID 1544"),
        ("ID 1545", 8.55, 9.85, "WHIMPER", "WHIMPER", "whimper_phrase_2", "Wavering canine whimper phrase from ID 1545"),
        ("ID 1545", 15.80, 17.20, "CRY", "CRY", "crying_phrase_2", "Intense crying and vocalization window from ID 1545"),
        ("ID 1546", 0.65, 1.45, "WHIMPER", "WHIMPER", "whimper_quiet_3", "Gentle whimpering onset from ID 1546"),
        ("ID 1546", 14.40, 15.65, "GROAN", "GROAN", "groan_plaintive", "Low plaintive groan/crying vocalization from ID 1546"),
        ("ID 1547", 1.70, 3.70, "PANT", "PANT", "pant_rhythmic", "Rhythmic canine breathing/panting clip from ID 1547"),
        ("ID 2450", 0.00, 0.90, "GROAN", "GROAN", "groan_deep_onset_1", "Deep vocal groan/howl onset (236.9 Hz dominant, 93% low-band) from ID 2450"),
        ("ID 2451", 0.00, 1.15, "GROAN", "GROAN", "groan_howl_onset", "Low-frequency vocal groan/howl onset (215 Hz dominant) from ID 2451"),
        ("ID 2451", 0.55, 2.30, "HOWL", "HOWL", "howl_sustained_2", "Sustained harmonic howl contour from ID 2451"),
        ("ID 0612", 1.95, 2.25, "YELP", "YELP", "yelp_sharp_small_dog", "Sharp high-pitched yelp burst from ID 0612"),
        ("ID 0682", 0.65, 1.20, "YIP", "YIP", "yip_spitz_doublet", "Spitz high-pitched yip doublet from ID 0682"),
        ("ID 2354", 0.02, 0.62, "BARK", "BARK", "bark_old_dog_doublet", "Clean two-burst bark from ID 2354"),
        ("ID 2352", 3.05, 3.85, "GRUNT", "GRUNT", "grunt_old_dog_chuff", "Old dog low vocal chuff/grunt from ID 2352"),
    ]

    extracted: list[dict[str, Any]] = []
    for sub, t0, t1, sug_cat, conf_cat, tag, note in specs:
        match_file = next((fname for fname in by_name if sub in fname), None)
        if not match_file:
            continue
        src_wav = by_name[match_file]
        y, sr = sf.read(str(src_wav), dtype="float32")
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        i0 = max(0, int(round(t0 * sr)))
        i1 = min(len(y), int(round(t1 * sr)))
        if i1 - i0 < int(0.10 * sr):
            continue
        clip = y[i0:i1].copy()
        # Apply gentle 6ms cosine edge taper to prevent boundary clicks
        fade = min(int(0.006 * sr), len(clip) // 6)
        if fade > 2:
            ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade, dtype=np.float32) / fade))
            clip[:fade] *= ramp
            clip[-fade:] *= ramp[::-1]
        extracted.append(
            {
                "clip": clip,
                "sr": int(sr),
                "source_filename": f"{match_file}#t={t0:.2f}-{t1:.2f}({tag})",
                "parent_filename": match_file,
                "suggested_category": sug_cat,
                "confirmed_category": conf_cat,
                "notes": note,
            }
        )
    return extracted


def build_or_load_reference_library(force_rebuild: bool = False) -> dict[str, Any]:
    """
    Build or load the Reference Audio Library manifest and processed assets.
    Preserves all original files unchanged.
    """
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None and not force_rebuild and REF_MANIFEST_JSON.exists():
        return _MANIFEST_CACHE

    REF_RAW_DIR.mkdir(parents=True, exist_ok=True)
    REF_PROC_DIR.mkdir(parents=True, exist_ok=True)
    REF_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    if not force_rebuild and REF_MANIFEST_JSON.exists():
        try:
            loaded = json.loads(REF_MANIFEST_JSON.read_text(encoding="utf-8"))
            if loaded.get("schema_version") == "2.1" and len(loaded.get("assets", [])) >= 30:
                for a in loaded.get("assets", []):
                    _normalize_asset_paths(a)
                _MANIFEST_CACHE = loaded
                return loaded
        except Exception:
            pass

    assets: list[dict[str, Any]] = []
    seen_raw_sha256: dict[str, str] = {}

    # 1. Ingest from data/datasets/v1/manifest.csv (32 BigSoundBank files + curated segments)
    v1_manifest = REPO_DATA_DIR / "datasets" / "v1" / "manifest.csv"
    v1_rows: list[dict[str, str]] = []
    if v1_manifest.exists():
        with v1_manifest.open("r", encoding="utf-8") as fh:
            v1_rows = list(csv.DictReader(fh))

    for row in v1_rows:
        src_path = Path(row["path"])
        if not src_path.exists():
            continue
        is_segment = "segment_of=" in (row.get("notes") or "")
        v_label = (row.get("vocalization_label") or row.get("label") or "").strip().lower()

        raw_bytes = src_path.read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        asset_id = row.get("sample_id") or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ref-{sha}"))
        orig_fname = row.get("source_filename") or src_path.name

        try:
            y, sr = sf.read(str(src_path), dtype="float32", always_2d=False)
            ch = 1 if y.ndim == 1 else int(y.shape[1])
            if y.ndim > 1:
                y = np.mean(y, axis=1)
            container_valid = True
        except Exception:
            container_valid = False
            y = np.zeros(0, dtype=np.float32)
            sr = TARGET_SR
            ch = 1

        # Copy processed WAV into reference_library/processed without altering source
        dest_proc = REF_PROC_DIR / f"{asset_id}.wav"
        if container_valid and y.size > 0:
            if not dest_proc.exists():
                sf.write(str(dest_proc), y.astype(np.float32), int(sr), subtype="PCM_16")
            proc_sha = hashlib.sha256(dest_proc.read_bytes()).hexdigest()
        else:
            proc_sha = sha

        profile = compute_reference_acoustic_profile(y, int(sr)) if container_valid and y.size > 0 else {"valid": False}
        td = profile.get("time_domain", {})
        dur = float(td.get("duration_sec", 0.0))
        peak = float(td.get("peak_amplitude", 0.0))
        rms = float(td.get("rms_energy", 0.0))
        clip_r = float(td.get("clipping_ratio", 0.0))
        sil_r = float(td.get("silence_ratio", 1.0))

        low_name = orig_fname.lower()
        is_non_canine = any(k in low_name for k in ("toymech", "squeaker", "couinement jouet", "pouet", "water fountain"))
        sug_cat, cat_note = suggest_vocalization_category(orig_fname, profile, manifest_hint=v_label)

        if not container_valid or y.size == 0:
            tech_status = "rejected_corrupt"
            conf_cat = None
            ann_status = "rejected"
        elif is_non_canine:
            tech_status = "rejected_non_canine"
            conf_cat = None
            ann_status = "excluded_non_canine"
        elif rms < 5e-4 or sil_r > 0.96:
            tech_status = "rejected_silent"
            conf_cat = None
            ann_status = "rejected"
        else:
            tech_status = "valid_canine_reference"
            conf_cat = sug_cat if row.get("annotation_status") == "reviewed" and sug_cat != "MIXED" else None
            ann_status = "human_reviewed" if conf_cat else "auto_suggested"

        seen_raw_sha256[row.get("file_hash") or sha] = asset_id
        seen_raw_sha256[sha] = asset_id

        assets.append(
            {
                "asset_id": asset_id,
                "original_filename": orig_fname,
                "provenance": row.get("source_dataset") or "32_sounds_BigSoundBank.com.zip",
                "is_segment": is_segment,
                "sha256": row.get("file_hash") or sha,
                "processed_sha256": proc_sha,
                "detected_format": row.get("format") or "wav",
                "container_valid": container_valid,
                "sample_rate": int(sr),
                "original_sample_rate": int(sr),
                "channels": 1,
                "original_channels": ch,
                "duration_sec": round(dur, 3),
                "peak_amplitude": round(peak, 4),
                "rms_energy": round(rms, 5),
                "clipping_ratio": round(clip_r, 5),
                "is_clipped": bool(clip_r > 0.02),
                "silence_ratio": round(sil_r, 4),
                "is_silent": bool(rms < 5e-4 or sil_r > 0.95),
                "suggested_category": sug_cat,
                "confirmed_category": conf_cat,
                "effective_category": conf_cat or sug_cat,
                "category_rationale": cat_note,
                "source_dog_id": row.get("dog_id") or "unknown",
                "recording_session_id": row.get("recording_session_id") or "unknown",
                "recording_conditions": "sound_library_field_or_indoor",
                "technical_validation_status": tech_status,
                "usage_rights_status": "reference_playback_and_variation_only_no_model_training",
                "annotation_status": ann_status,
                "processed_path": str(dest_proc),
                "notes": row.get("notes") or "",
                "acoustic_profile": profile,
            }
        )

    # 2. Extract targeted focal sub-clips for underrepresented categories (GROWL, GRUNT, GROAN, WHIMPER, CRY, PANT, YELP)
    focal_clips = _extract_focal_subclips(v1_rows)
    for fc in focal_clips:
        clip_y = fc["clip"]
        sr = fc["sr"]
        orig_fname = fc["source_filename"]
        asset_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"focal-{orig_fname}"))
        dest_proc = REF_PROC_DIR / f"{asset_id}.wav"
        sf.write(str(dest_proc), clip_y.astype(np.float32), sr, subtype="PCM_16")
        raw_bytes = dest_proc.read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        profile = compute_reference_acoustic_profile(clip_y, sr)
        td = profile.get("time_domain", {})
        assets.append(
            {
                "asset_id": asset_id,
                "original_filename": orig_fname,
                "provenance": f"curated_segment_from:{fc['parent_filename']}",
                "is_segment": True,
                "sha256": sha,
                "processed_sha256": sha,
                "detected_format": "wav",
                "container_valid": True,
                "sample_rate": sr,
                "original_sample_rate": sr,
                "channels": 1,
                "original_channels": 1,
                "duration_sec": round(float(td.get("duration_sec", 0.0)), 3),
                "peak_amplitude": round(float(td.get("peak_amplitude", 0.0)), 4),
                "rms_energy": round(float(td.get("rms_energy", 0.0)), 5),
                "clipping_ratio": round(float(td.get("clipping_ratio", 0.0)), 5),
                "is_clipped": bool(float(td.get("clipping_ratio", 0.0)) > 0.02),
                "silence_ratio": round(float(td.get("silence_ratio", 0.0)), 4),
                "is_silent": False,
                "suggested_category": fc["suggested_category"],
                "confirmed_category": fc["confirmed_category"],
                "effective_category": fc["confirmed_category"] or fc["suggested_category"],
                "category_rationale": fc["notes"],
                "source_dog_id": "curated_reference",
                "recording_session_id": fc["parent_filename"],
                "recording_conditions": "curated_vocalization_window",
                "technical_validation_status": "valid_canine_reference",
                "usage_rights_status": "reference_playback_and_variation_only_no_model_training",
                "annotation_status": "human_reviewed",
                "processed_path": str(dest_proc),
                "notes": fc["notes"],
                "acoustic_profile": profile,
            }
        )

    # 3. Ingest supplied standalone, Pixabay user-provided, & archive dog recordings from Downloads if available
    downloads_dir = Path(r"C:\Users\Admin\Downloads")
    external_items: list[tuple[str, str, bytes, str | None, str | None]] = []
    for standalone in ("a dog.mp3", "dog.mp3"):
        sp = downloads_dir / standalone
        if sp.exists() and sp.is_file():
            external_items.append((standalone, "Downloads_standalone", sp.read_bytes(), None, None))

    pixabay_user_files = [
        (
            "scottishperson-sound-effect-dog-deep-barking-01-367309.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=scottishperson, id=367309, url=https://pixabay.com/sound-effects/sound-effect-dog-deep-barking-01-367309/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "audiopapkin-german-shepherd-barking-302356.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=audiopapkin, id=302356, url=https://pixabay.com/sound-effects/german-shepherd-barking-302356/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "dragon-studio-dogs-barking-03-494310.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=dragon-studio, id=494310, url=https://pixabay.com/sound-effects/dogs-barking-03-494310/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "spinopel-dog-barking-at-cat-336373.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=spinopel, id=336373, url=https://pixabay.com/sound-effects/dog-barking-at-cat-336373/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "audiopapkin-barking-large-and-small-dog-290711.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=audiopapkin, id=290711, url=https://pixabay.com/sound-effects/barking-large-and-small-dog-290711/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "dragon-studio-dog-barking-406629.mp3",
            "BARK",
            "User-supplied Pixabay reference (creator=dragon-studio, id=406629, url=https://pixabay.com/sound-effects/dog-barking-406629/, license=Pixabay Content License — reference playback/variation permitted; ML training not authorized)",
        ),
        (
            "dragon-studio-dog-barking-406629 (1).mp3",
            "BARK",
            "Duplicate copy of dragon-studio-dog-barking-406629.mp3 (excluded via SHA-256 deduplication)",
        ),
    ]
    for px_fname, px_cat, px_note in pixabay_user_files:
        px_path = downloads_dir / px_fname
        if px_path.exists() and px_path.is_file():
            external_items.append((px_fname, "Pixabay_User_Supplied", px_path.read_bytes(), px_cat, px_note))

    for zname in ("dog recode.zip", "dog reg 2.zip"):
        zp = downloads_dir / zname
        if zp.exists() and zp.is_file():
            try:
                with zipfile.ZipFile(zp) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        ext = Path(info.filename).suffix.lower()
                        if ext in {".mp3", ".mpeg", ".wav", ".ogg", ".m4a", ".flac", ".webm"}:
                            conf_override = "GRUNT" if "7.51.17 PM (2)" in info.filename else None
                            note_override = (
                                "Verified low-frequency canine vocal grunt (172.3 Hz dominant)"
                                if conf_override
                                else None
                            )
                            external_items.append((info.filename, zname, zf.read(info.filename), conf_override, note_override))
            except Exception:
                pass

    # Curated, acoustically verified high-SNR clips from supplied archive\cats_dogs\train\dog and archive (1)\DvC\Dogs
    curated_external_dirs: list[tuple[Path, str, list[tuple[str, str, str]]]] = [
        (
            downloads_dir / "archive" / "cats_dogs" / "train" / "dog",
            "archive_cats_dogs_train_dog",
            [
                ("dog_barking_109.wav", "GROWL", "Deep sustained low-frequency canine growl (86.1 Hz dominant, 100% low-band energy)"),
                ("dog_barking_13.wav", "HOWL", "Sustained harmonic canine howl (609 Hz F0, 13.7 dB HNR)"),
                ("dog_barking_29.wav", "HOWL", "Sustained melodic canine howl (582 Hz F0, 12.2 dB HNR)"),
                ("dog_barking_76.wav", "CRY", "High-pitched distress crying vocalization (629 Hz F0, 11.7 dB HNR)"),
                ("dog_barking_10.wav", "BARK", "Clear rhythmic medium-dog barking sequence (542 Hz F0)"),
                ("dog_barking_47.wav", "BARK", "Resonant deep-chested dog bark sequence (454 Hz F0)"),
            ],
        ),
        (
            downloads_dir / "archive (1)" / "DvC" / "Dogs",
            "archive_DvC_Dogs",
            [
                ("dog0186.wav", "GRUNT", "Low-frequency canine vocal grunt (129.2 Hz dominant, 76% low-band energy)"),
                ("dog0387.wav", "GROAN", "Low-pitched sustained canine groan (323.0 Hz dominant, 57% low-band energy)"),
                ("dog0031.wav", "WHIMPER", "Plaintive high-frequency canine whimper (633 Hz F0, 15.6 dB HNR)"),
                ("dog0044.wav", "WHIMPER", "Soft wavering canine whimper phrase (705 Hz F0, 16.0 dB HNR)"),
                ("dog0089.wav", "WHIMPER", "Repeated high-pitched whimpering pulses (693 Hz F0, 15.6 dB HNR)"),
                ("dog0091.wav", "CRY", "Intense high-pitched canine cry (630 Hz F0, 15.9 dB HNR)"),
                ("dog0280.wav", "CRY", "Sustained plaintive canine cry vocalization (613 Hz F0, 12.2 dB HNR)"),
                ("dog0050.wav", "WHINE", "High-HNR narrow-band canine whine (692 Hz F0, 16.6 dB HNR)"),
                ("dog0054.wav", "WHINE", "Pure tonal canine whine contour (685 Hz F0, 16.6 dB HNR)"),
                ("dog0060.wav", "WHINE", "Sustained high-pitched canine whine (657 Hz F0, 16.3 dB HNR)"),
                ("dog0147.wav", "YELP", "Sharp high-frequency canine yelp burst (1439 Hz F0, 11.4 dB HNR)"),
                ("dog0149.wav", "YELP", "High-intensity sharp canine yelp (1446 Hz F0, 11.7 dB HNR)"),
                ("dog0246.wav", "YELP", "Compact high-pitched canine yelp (1417 Hz F0, 10.6 dB HNR)"),
                ("dog0073.wav", "YIP", "Short high-pitched small-dog yip burst (874 Hz F0, 15.2 dB HNR)"),
                ("dog0074.wav", "YIP", "Bright small-dog yip vocalization (832 Hz F0, 15.5 dB HNR)"),
                ("dog0011.wav", "BARK", "Crisp single-dog bark vocalization (666 Hz F0, 81% active)"),
            ],
        ),
    ]
    for folder_path, prov_tag, file_specs in curated_external_dirs:
        if folder_path.exists() and folder_path.is_dir():
            for fname, conf_cat, rationale_note in file_specs:
                fp = folder_path / fname
                if fp.exists() and fp.is_file():
                    external_items.append((fname, prov_tag, fp.read_bytes(), conf_cat, rationale_note))

    for orig_fname, source_prov, data, conf_override, note_override in external_items:
        sha = hashlib.sha256(data).hexdigest()
        asset_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ext-{source_prov}-{orig_fname}-{sha[:12]}"))
        is_dup = sha in seen_raw_sha256
        dup_of = seen_raw_sha256.get(sha)
        if not is_dup:
            seen_raw_sha256[sha] = asset_id

        suffix = Path(orig_fname).suffix.lower() or ".mp3"
        raw_dest = REF_RAW_DIR / f"{asset_id}{suffix}"
        proc_dest = REF_PROC_DIR / f"{asset_id}.wav"
        if not raw_dest.exists():
            raw_dest.write_bytes(data)

        try:
            fmt = sniff_format(data[:64], orig_fname)
            if proc_dest.exists():
                y, sr = sf.read(str(proc_dest), dtype="float32", always_2d=False)
                orig_sr = int(sr)
                orig_ch = 1
            else:
                y_raw, orig_sr = _decode_any(raw_dest, proc_dest, fmt)
                orig_ch = 1 if y_raw.ndim == 1 else int(y_raw.shape[1])
                y, _ = preprocess(y_raw, orig_sr)
                sr = TARGET_SR
                sf.write(str(proc_dest), y.astype(np.float32), sr, subtype="PCM_16")
            container_valid = True
            proc_sha = hashlib.sha256(proc_dest.read_bytes()).hexdigest()
        except Exception:
            container_valid = False
            fmt = suffix.lstrip(".")
            y = np.zeros(0, dtype=np.float32)
            sr = TARGET_SR
            orig_sr = TARGET_SR
            orig_ch = 1
            proc_sha = sha

        profile = compute_reference_acoustic_profile(y, int(sr)) if container_valid and y.size > 0 else {"valid": False}
        td = profile.get("time_domain", {})
        dur = float(td.get("duration_sec", 0.0))
        peak = float(td.get("peak_amplitude", 0.0))
        rms = float(td.get("rms_energy", 0.0))
        clip_r = float(td.get("clipping_ratio", 0.0))
        sil_r = float(td.get("silence_ratio", 1.0))

        sug_cat, cat_note = suggest_vocalization_category(orig_fname, profile, manifest_hint=conf_override)
        if note_override:
            cat_note = note_override
        if not container_valid or y.size == 0:
            tech_status = "rejected_corrupt"
        elif is_dup:
            tech_status = "rejected_duplicate"
        elif rms < 5e-4 or sil_r > 0.95:
            tech_status = "rejected_silent"
        else:
            tech_status = "valid_canine_reference"

        conf_cat_val = conf_override if (conf_override and tech_status == "valid_canine_reference") else None
        ann_status_val = (
            "duplicate"
            if is_dup
            else ("human_reviewed" if conf_cat_val else "auto_suggested")
        )

        assets.append(
            {
                "asset_id": asset_id,
                "original_filename": orig_fname,
                "provenance": source_prov,
                "owner_user_id": None,
                "is_segment": False,
                "sha256": sha,
                "processed_sha256": proc_sha,
                "detected_format": fmt,
                "container_valid": container_valid,
                "sample_rate": int(sr),
                "original_sample_rate": int(orig_sr),
                "channels": 1,
                "original_channels": int(orig_ch),
                "duration_sec": round(dur, 3),
                "peak_amplitude": round(peak, 4),
                "rms_energy": round(rms, 5),
                "clipping_ratio": round(clip_r, 5),
                "is_clipped": bool(clip_r > 0.02),
                "silence_ratio": round(sil_r, 4),
                "is_silent": bool(rms < 5e-4 or sil_r > 0.95),
                "suggested_category": sug_cat,
                "confirmed_category": conf_cat_val,
                "effective_category": conf_cat_val or sug_cat,
                "category_rationale": cat_note,
                "source_dog_id": f"field-{sha[:8]}",
                "recording_session_id": f"session-{source_prov}",
                "recording_conditions": "curated_external_archive" if conf_override else "user_supplied_field_recording",
                "technical_validation_status": tech_status,
                "usage_rights_status": "user_supplied_reference_playback_and_variation_only",
                "annotation_status": ann_status_val,
                "processed_path": str(proc_dest),
                "notes": f"duplicate_of={dup_of}" if is_dup else (note_override or ""),
                "acoustic_profile": profile,
            }
        )

    manifest_data = _finalize_and_save_manifest(assets)
    _MANIFEST_CACHE = manifest_data
    return manifest_data


def _finalize_and_save_manifest(assets: list[dict[str, Any]]) -> dict[str, Any]:
    for a in assets:
        if "owner_user_id" not in a:
            a["owner_user_id"] = None
    valid_assets = [
        a
        for a in assets
        if a["technical_validation_status"] == "valid_canine_reference" and a.get("owner_user_id") is None
    ]
    rejected_assets = [
        a
        for a in assets
        if a["technical_validation_status"] != "valid_canine_reference" and a.get("owner_user_id") is None
    ]

    category_counts: dict[str, int] = {cat: 0 for cat in SUPPORTED_REFERENCE_CATEGORIES}
    confirmed_counts: dict[str, int] = {cat: 0 for cat in SUPPORTED_REFERENCE_CATEGORIES}
    for a in valid_assets:
        eff = a.get("effective_category") or "UNKNOWN"
        if eff in category_counts:
            category_counts[eff] += 1
        if a.get("confirmed_category") in confirmed_counts:
            confirmed_counts[a["confirmed_category"]] += 1

    rejection_breakdown: dict[str, int] = {}
    for a in rejected_assets:
        st = a["technical_validation_status"]
        rejection_breakdown[st] = rejection_breakdown.get(st, 0) + 1

    manifest_data = {
        "schema_version": "2.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_inspected": len(valid_assets) + len(rejected_assets),
        "total_accepted_canine_references": len(valid_assets),
        "total_rejected": len(rejected_assets),
        "rejection_breakdown": rejection_breakdown,
        "category_counts": category_counts,
        "confirmed_category_counts": confirmed_counts,
        "supported_categories": list(SUPPORTED_REFERENCE_CATEGORIES),
        "assets": assets,
    }

    with _MANIFEST_WRITE_LOCK:
        tmp_json = REF_MANIFEST_JSON.with_suffix(".json.tmp")
        tmp_json.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        os.replace(tmp_json, REF_MANIFEST_JSON)

    csv_fields = [
        "asset_id",
        "original_filename",
        "provenance",
        "owner_user_id",
        "sha256",
        "detected_format",
        "sample_rate",
        "channels",
        "duration_sec",
        "peak_amplitude",
        "rms_energy",
        "is_clipped",
        "is_silent",
        "suggested_category",
        "confirmed_category",
        "effective_category",
        "source_dog_id",
        "recording_session_id",
        "recording_conditions",
        "technical_validation_status",
        "usage_rights_status",
        "annotation_status",
        "notes",
    ]
    with REF_MANIFEST_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_fields)
        w.writeheader()
        for a in assets:
            w.writerow({k: a.get(k, "") for k in csv_fields})

    return manifest_data


def purge_user_references(user_id: str) -> int:
    """
    Delete every private reference upload owned by `user_id` (raw, processed, plots and manifest rows).
    Shared library assets (owner_user_id is None) and other users' assets are never touched.
    """
    global _MANIFEST_CACHE
    if not user_id:
        return 0
    with _MANIFEST_WRITE_LOCK:
        lib = build_or_load_reference_library()
        assets = lib.get("assets", [])
        mine = [a for a in assets if a.get("owner_user_id") == user_id]
        if not mine:
            return 0
        for a in mine:
            aid = a["asset_id"]
            Path(a.get("processed_path", "")).unlink(missing_ok=True)
            for p in REF_RAW_DIR.glob(f"{aid}.*"):
                p.unlink(missing_ok=True)
            for p in REF_PLOTS_DIR.glob(f"{aid}*"):
                p.unlink(missing_ok=True)
        keep = [a for a in assets if a.get("owner_user_id") != user_id]
        _MANIFEST_CACHE = _finalize_and_save_manifest(keep)
        return len(mine)


def is_reference_accessible(asset: dict[str, Any], user_id: str | None = None) -> bool:
    """
    Shared dataset references (`owner_user_id is None`) are accessible to all authenticated users.
    User-uploaded reference recordings (`owner_user_id != None`) are strictly isolated to the uploading user.
    """
    owner = asset.get("owner_user_id")
    if owner is None:
        return True
    return bool(user_id and owner == user_id)


def get_reference_asset(asset_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    lib = build_or_load_reference_library()
    for a in lib.get("assets", []):
        if a["asset_id"] == asset_id:
            if not is_reference_accessible(a, user_id):
                return None
            return _normalize_asset_paths(a)
    return None


def update_reference_asset_annotation(
    asset_id: str,
    confirmed_category: str | None = None,
    notes: str | None = None,
    reviewer: str = "user_review",
    user_id: str | None = None,
) -> dict[str, Any]:
    """Allow the user to review and correct vocalization category labels without altering raw audio."""
    global _MANIFEST_CACHE
    lib = build_or_load_reference_library()
    assets = lib.get("assets", [])
    target = None
    for a in assets:
        if a["asset_id"] == asset_id:
            if not is_reference_accessible(a, user_id):
                raise KeyError(f"Reference asset '{asset_id}' not found.")
            if a.get("owner_user_id") is None:
                # Shared library assets are read-only for API users: relabelling would silently change
                # Engine B results for every other user.
                raise PermissionError("Shared library references are read-only.")
            target = a
            break
    if target is None:
        raise KeyError(f"Reference asset '{asset_id}' not found.")

    if confirmed_category is not None:
        cat_clean = confirmed_category.strip().upper()
        if cat_clean == "" or cat_clean == "CLEAR":
            target["confirmed_category"] = None
            target["effective_category"] = target["suggested_category"]
            target["annotation_status"] = "auto_suggested"
        else:
            if cat_clean not in SUPPORTED_REFERENCE_CATEGORIES:
                raise ValueError(f"Unsupported category '{confirmed_category}'. Must be one of {SUPPORTED_REFERENCE_CATEGORIES}.")
            target["confirmed_category"] = cat_clean
            target["effective_category"] = cat_clean
            target["annotation_status"] = "human_reviewed"
            target["reviewed_by"] = reviewer

    if notes is not None:
        target["notes"] = notes.strip()[:500]

    _MANIFEST_CACHE = _finalize_and_save_manifest(assets)
    return target


def ingest_user_reference_file(
    data: bytes,
    filename: str,
    confirmed_category: str | None = None,
    source_dog_id: str | None = None,
    recording_conditions: str | None = None,
    owner_user_id: str | None = None,
) -> dict[str, Any]:
    """Ingest a user-uploaded dog recording into the Reference Audio Library safely with per-user ownership isolation."""
    global _MANIFEST_CACHE
    if not data or len(data) < 64:
        raise ValueError("Uploaded reference file is empty or too small.")

    fmt = sniff_format(data[:64], filename)
    sha = hashlib.sha256(data).hexdigest()
    lib = build_or_load_reference_library()
    assets = lib.get("assets", [])

    # Check if already present by SHA-256 FOR THIS SAME OWNER (never expose another user's private upload)
    for existing in assets:
        if (
            existing["sha256"] == sha
            and existing["technical_validation_status"] == "valid_canine_reference"
            and existing.get("owner_user_id") == owner_user_id
        ):
            if confirmed_category:
                return update_reference_asset_annotation(
                    existing["asset_id"],
                    confirmed_category=confirmed_category,
                    user_id=owner_user_id,
                )
            return existing

    asset_id = str(uuid.uuid4())
    ext = Path(filename).suffix.lower() or f".{fmt}"
    raw_dest = REF_RAW_DIR / f"{asset_id}{ext}"
    proc_dest = REF_PROC_DIR / f"{asset_id}.wav"
    raw_dest.write_bytes(data)

    y_raw, orig_sr = _decode_any(raw_dest, proc_dest, fmt)
    orig_ch = 1 if y_raw.ndim == 1 else int(y_raw.shape[1])
    y, _ = preprocess(y_raw, orig_sr)
    sf.write(str(proc_dest), y.astype(np.float32), TARGET_SR, subtype="PCM_16")
    proc_sha = hashlib.sha256(proc_dest.read_bytes()).hexdigest()

    profile = compute_reference_acoustic_profile(y, TARGET_SR)
    td = profile.get("time_domain", {})
    rms = float(td.get("rms_energy", 0.0))
    sil_r = float(td.get("silence_ratio", 1.0))
    if rms < 5e-4 or sil_r > 0.95:
        raw_dest.unlink(missing_ok=True)
        proc_dest.unlink(missing_ok=True)
        raise ValueError("Uploaded reference recording is silent or near-silent and cannot be used as a reference.")

    sug_cat, rationale = suggest_vocalization_category(filename, profile)
    conf_cat = None
    if confirmed_category and confirmed_category.strip():
        c_up = confirmed_category.strip().upper()
        if c_up not in SUPPORTED_REFERENCE_CATEGORIES:
            raise ValueError(f"Unsupported category '{confirmed_category}'.")
        conf_cat = c_up

    new_asset = {
        "asset_id": asset_id,
        "original_filename": filename[:240],
        "provenance": "user_uploaded_reference",
        "owner_user_id": owner_user_id,
        "is_segment": False,
        "sha256": sha,
        "processed_sha256": proc_sha,
        "detected_format": fmt,
        "container_valid": True,
        "sample_rate": TARGET_SR,
        "original_sample_rate": int(orig_sr),
        "channels": 1,
        "original_channels": int(orig_ch),
        "duration_sec": round(float(td.get("duration_sec", 0.0)), 3),
        "peak_amplitude": round(float(td.get("peak_amplitude", 0.0)), 4),
        "rms_energy": round(rms, 5),
        "clipping_ratio": round(float(td.get("clipping_ratio", 0.0)), 5),
        "is_clipped": bool(float(td.get("clipping_ratio", 0.0)) > 0.02),
        "silence_ratio": round(sil_r, 4),
        "is_silent": False,
        "suggested_category": sug_cat,
        "confirmed_category": conf_cat,
        "effective_category": conf_cat or sug_cat,
        "category_rationale": rationale,
        "source_dog_id": source_dog_id or "user_dog",
        "recording_session_id": f"upload-{asset_id[:8]}",
        "recording_conditions": recording_conditions or "user_uploaded",
        "technical_validation_status": "valid_canine_reference",
        "usage_rights_status": "user_uploaded_reference_playback_and_variation_only",
        "annotation_status": "human_reviewed" if conf_cat else "auto_suggested",
        "processed_path": str(proc_dest),
        "notes": "User-uploaded reference recording",
        "acoustic_profile": profile,
    }
    assets.insert(0, new_asset)
    _MANIFEST_CACHE = _finalize_and_save_manifest(assets)
    return new_asset
