"""
Engine B â€” Parametric DSP Fallback & WAV Validation Utilities.

NOTE: The primary Engine B generation strategy is now Reference-Driven Generation
(`reference_engine.py`: Method A `reference_direct` and Method B `reference_variation`).
This module provides:
1. Repaired experimental DSP synthesis (`experimental_dsp` mode) that eliminates the
   "breaking-stick" crackle caused previously by 48% continuous broadband white noise
   fed into series-cascaded high-Q IIR filters. Instead, it uses a smooth Rosenberg
   glottal pulse waveform, parallel moderate-Q formant resonators, and onset-only
   low-level aspiration.
2. Deterministic parameter calculation (`calculate_synthesis_parameters`).
3. On-disk WAV integrity and transient/discontinuity validation (`validate_generated_wav`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter

from .. import SYNTH_MODEL_VERSION
from ..config import TARGET_SR

SUPPORTED_PROFILES: tuple[str, ...] = (
    "bark",
    "growl",
    "whine",
    "howl",
    "yip",
    "yelp",
    "whimper",
    "cry",
    "grunt",
    "groan",
    "pant",
    "soft_attention",
)

# Repaired acoustic templates with natural formant bandwidths and low onset-only aspiration
_PROFILE_TEMPLATES: dict[str, dict[str, Any]] = {
    "bark": {
        "description": "Rosenberg glottal pulse bursts with parallel vocal-tract formants and soft onset aspiration.",
        "duration": 1.15,
        "f0_base_hz": 360.0,
        "f0_end_hz": 430.0,
        "f0_trajectory": "stepped_bursts",
        "harmonics": 10,
        "harmonic_rolloff_db": 8.5,
        "formants_hz": [680.0, 1420.0, 2450.0],
        "bandwidths_hz": [190.0, 280.0, 420.0],
        "noise_ratio": 0.06,
        "noise_band_hz": [280.0, 1800.0],
        "fm_rate_hz": 4.5,
        "fm_depth_hz": 7.0,
        "am_rate_hz": 0.0,
        "am_depth": 0.0,
        "attack_sec": 0.022,
        "decay_sec": 0.075,
        "sustain_level": 0.42,
        "release_sec": 0.065,
        "n_events": 3,
        "gap_sec": 0.16,
        "default_intensity": 0.82,
    },
    "growl": {
        "description": "Low-fundamental vocal fold vibration with subharmonics, 28 Hz amplitude modulation, and warm low formants.",
        "duration": 1.50,
        "f0_base_hz": 115.0,
        "f0_end_hz": 124.0,
        "f0_trajectory": "low_modulated",
        "harmonics": 12,
        "harmonic_rolloff_db": 7.5,
        "formants_hz": [320.0, 780.0, 1520.0],
        "bandwidths_hz": [140.0, 220.0, 340.0],
        "noise_ratio": 0.05,
        "noise_band_hz": [110.0, 950.0],
        "fm_rate_hz": 3.2,
        "fm_depth_hz": 5.0,
        "am_rate_hz": 28.0,
        "am_depth": 0.35,
        "attack_sec": 0.090,
        "decay_sec": 0.220,
        "sustain_level": 0.80,
        "release_sec": 0.200,
        "n_events": 1,
        "gap_sec": 0.0,
        "default_intensity": 0.78,
    },
    "whine": {
        "description": "High-frequency tonal glottal contour with rising pitch trajectory and gentle vibrato.",
        "duration": 1.05,
        "f0_base_hz": 680.0,
        "f0_end_hz": 960.0,
        "f0_trajectory": "rising_arch",
        "harmonics": 7,
        "harmonic_rolloff_db": 11.0,
        "formants_hz": [1050.0, 2150.0, 3200.0],
        "bandwidths_hz": [180.0, 260.0, 380.0],
        "noise_ratio": 0.02,
        "noise_band_hz": [500.0, 2600.0],
        "fm_rate_hz": 6.0,
        "fm_depth_hz": 12.0,
        "am_rate_hz": 4.8,
        "am_depth": 0.08,
        "attack_sec": 0.075,
        "decay_sec": 0.140,
        "sustain_level": 0.84,
        "release_sec": 0.160,
        "n_events": 1,
        "gap_sec": 0.0,
        "default_intensity": 0.72,
    },
    "howl": {
        "description": "Sustained harmonic vocalization with smooth pitch glide and warm mid-band resonances.",
        "duration": 2.20,
        "f0_base_hz": 360.0,
        "f0_end_hz": 540.0,
        "f0_trajectory": "sustained_arch",
        "harmonics": 9,
        "harmonic_rolloff_db": 9.5,
        "formants_hz": [620.0, 1280.0, 2180.0],
        "bandwidths_hz": [150.0, 230.0, 340.0],
        "noise_ratio": 0.02,
        "noise_band_hz": [240.0, 1800.0],
        "fm_rate_hz": 2.6,
        "fm_depth_hz": 9.0,
        "am_rate_hz": 1.8,
        "am_depth": 0.06,
        "attack_sec": 0.240,
        "decay_sec": 0.280,
        "sustain_level": 0.88,
        "release_sec": 0.340,
        "n_events": 1,
        "gap_sec": 0.0,
        "default_intensity": 0.82,
    },
    "yip": {
        "description": "Short, high-pitched arched harmonic vocalization with smooth attack and decay.",
        "duration": 0.42,
        "f0_base_hz": 780.0,
        "f0_end_hz": 980.0,
        "f0_trajectory": "rapid_arch",
        "harmonics": 6,
        "harmonic_rolloff_db": 10.5,
        "formants_hz": [1250.0, 2350.0, 3400.0],
        "bandwidths_hz": [210.0, 300.0, 420.0],
        "noise_ratio": 0.04,
        "noise_band_hz": [600.0, 2800.0],
        "fm_rate_hz": 6.5,
        "fm_depth_hz": 10.0,
        "am_rate_hz": 0.0,
        "am_depth": 0.0,
        "attack_sec": 0.018,
        "decay_sec": 0.045,
        "sustain_level": 0.48,
        "release_sec": 0.050,
        "n_events": 2,
        "gap_sec": 0.10,
        "default_intensity": 0.76,
    },
    "yelp": {
        "description": "Sharp high-pitched arched vocalization with rapid inflection.",
        "duration": 0.38,
        "f0_base_hz": 880.0,
        "f0_end_hz": 1140.0,
        "f0_trajectory": "rapid_arch",
        "harmonics": 6,
        "harmonic_rolloff_db": 10.0,
        "formants_hz": [1320.0, 2480.0, 3550.0],
        "bandwidths_hz": [220.0, 310.0, 430.0],
        "noise_ratio": 0.04,
        "noise_band_hz": [650.0, 3000.0],
        "fm_rate_hz": 7.0,
        "fm_depth_hz": 12.0,
        "am_rate_hz": 0.0,
        "am_depth": 0.0,
        "attack_sec": 0.016,
        "decay_sec": 0.050,
        "sustain_level": 0.45,
        "release_sec": 0.055,
        "n_events": 1,
        "gap_sec": 0.08,
        "default_intensity": 0.78,
    },
    "whimper": {
        "description": "Gentle wavering plaintive contour with repeated soft tonal pulses.",
        "duration": 0.85,
        "f0_base_hz": 580.0,
        "f0_end_hz": 720.0,
        "f0_trajectory": "gentle_doublet",
        "harmonics": 7,
        "harmonic_rolloff_db": 10.5,
        "formants_hz": [880.0, 1820.0, 2850.0],
        "bandwidths_hz": [180.0, 260.0, 380.0],
        "noise_ratio": 0.03,
        "noise_band_hz": [400.0, 2200.0],
        "fm_rate_hz": 6.2,
        "fm_depth_hz": 11.0,
        "am_rate_hz": 5.5,
        "am_depth": 0.14,
        "attack_sec": 0.040,
        "decay_sec": 0.080,
        "sustain_level": 0.68,
        "release_sec": 0.090,
        "n_events": 2,
        "gap_sec": 0.11,
        "default_intensity": 0.68,
    },
    "cry": {
        "description": "Sustained plaintive high-pitched vocalization with descending tail.",
        "duration": 1.25,
        "f0_base_hz": 720.0,
        "f0_end_hz": 590.0,
        "f0_trajectory": "rising_arch",
        "harmonics": 7,
        "harmonic_rolloff_db": 10.0,
        "formants_hz": [980.0, 2040.0, 3100.0],
        "bandwidths_hz": [185.0, 270.0, 390.0],
        "noise_ratio": 0.03,
        "noise_band_hz": [450.0, 2500.0],
        "fm_rate_hz": 6.4,
        "fm_depth_hz": 13.0,
        "am_rate_hz": 4.2,
        "am_depth": 0.12,
        "attack_sec": 0.060,
        "decay_sec": 0.140,
        "sustain_level": 0.78,
        "release_sec": 0.160,
        "n_events": 2,
        "gap_sec": 0.14,
        "default_intensity": 0.74,
    },
    "grunt": {
        "description": "Short, low-frequency damped vocal pulse with warm low-band formant energy.",
        "duration": 0.36,
        "f0_base_hz": 125.0,
        "f0_end_hz": 98.0,
        "f0_trajectory": "falling_pulse",
        "harmonics": 8,
        "harmonic_rolloff_db": 9.0,
        "formants_hz": [320.0, 740.0, 1420.0],
        "bandwidths_hz": [150.0, 230.0, 340.0],
        "noise_ratio": 0.06,
        "noise_band_hz": [100.0, 900.0],
        "fm_rate_hz": 2.2,
        "fm_depth_hz": 4.0,
        "am_rate_hz": 18.0,
        "am_depth": 0.16,
        "attack_sec": 0.024,
        "decay_sec": 0.070,
        "sustain_level": 0.45,
        "release_sec": 0.065,
        "n_events": 1,
        "gap_sec": 0.12,
        "default_intensity": 0.72,
    },
    "groan": {
        "description": "Sustained low-frequency vocal groan with gradual downward pitch drift.",
        "duration": 1.10,
        "f0_base_hz": 165.0,
        "f0_end_hz": 128.0,
        "f0_trajectory": "falling_pulse",
        "harmonics": 9,
        "harmonic_rolloff_db": 8.5,
        "formants_hz": [360.0, 820.0, 1580.0],
        "bandwidths_hz": [155.0, 240.0, 350.0],
        "noise_ratio": 0.04,
        "noise_band_hz": [110.0, 1050.0],
        "fm_rate_hz": 2.8,
        "fm_depth_hz": 5.0,
        "am_rate_hz": 14.0,
        "am_depth": 0.15,
        "attack_sec": 0.085,
        "decay_sec": 0.180,
        "sustain_level": 0.74,
        "release_sec": 0.190,
        "n_events": 1,
        "gap_sec": 0.0,
        "default_intensity": 0.74,
    },
    "pant": {
        "description": "Rhythmic low-tonality respiratory airflow pulses.",
        "duration": 1.20,
        "f0_base_hz": 140.0,
        "f0_end_hz": 135.0,
        "f0_trajectory": "falling_pulse",
        "harmonics": 5,
        "harmonic_rolloff_db": 11.0,
        "formants_hz": [420.0, 1150.0, 2100.0],
        "bandwidths_hz": [260.0, 380.0, 520.0],
        "noise_ratio": 0.18,
        "noise_band_hz": [180.0, 1600.0],
        "fm_rate_hz": 1.5,
        "fm_depth_hz": 3.0,
        "am_rate_hz": 0.0,
        "am_depth": 0.0,
        "attack_sec": 0.045,
        "decay_sec": 0.075,
        "sustain_level": 0.50,
        "release_sec": 0.065,
        "n_events": 4,
        "gap_sec": 0.09,
        "default_intensity": 0.65,
    },
    "soft_attention": {
        "description": "Gentle two-note mid-frequency harmonic cue with soft attack/release.",
        "duration": 0.72,
        "f0_base_hz": 440.0,
        "f0_end_hz": 530.0,
        "f0_trajectory": "gentle_doublet",
        "harmonics": 7,
        "harmonic_rolloff_db": 10.5,
        "formants_hz": [660.0, 1420.0, 2450.0],
        "bandwidths_hz": [180.0, 260.0, 380.0],
        "noise_ratio": 0.03,
        "noise_band_hz": [250.0, 1800.0],
        "fm_rate_hz": 4.5,
        "fm_depth_hz": 8.0,
        "am_rate_hz": 0.0,
        "am_depth": 0.0,
        "attack_sec": 0.040,
        "decay_sec": 0.075,
        "sustain_level": 0.68,
        "release_sec": 0.085,
        "n_events": 2,
        "gap_sec": 0.11,
        "default_intensity": 0.68,
    },
}

_INTENT_MODIFIERS: dict[str, dict[str, Any]] = {
    "come": {"n_events": 3, "f0_scale": 1.06, "duration_scale": 0.95},
    "attention": {"n_events": 2, "f0_scale": 1.04, "duration_scale": 0.90},
    "stay": {"n_events": 1, "f0_scale": 0.96, "duration_scale": 1.05},
    "stop": {"n_events": 1, "f0_scale": 0.94, "duration_scale": 1.0},
    "play": {"n_events": 2, "f0_scale": 1.05, "duration_scale": 1.35},
    "positive_reinforcement": {"n_events": 1, "f0_scale": 1.03, "duration_scale": 1.0},
    "calm": {"n_events": 1, "f0_scale": 0.95, "duration_scale": 1.05},
}


def calculate_synthesis_parameters(
    vocalization: str,
    intent: str | None = None,
    sr: int = TARGET_SR,
    intensity: float | None = None,
    duration_sec: float | None = None,
    pitch_hz: float | None = None,
) -> dict[str, Any]:
    """Deterministically calculate and validate parameters for Engine B."""
    voc = (vocalization or "bark").strip().lower()
    if voc not in _PROFILE_TEMPLATES:
        voc = "bark"

    if not isinstance(sr, (int, float)) or int(sr) < 8000 or int(sr) > 48000:
        raise ValueError(f"Sample rate must be between 8000 and 48000 Hz (got {sr}).")
    sr = int(sr)

    tpl = dict(_PROFILE_TEMPLATES[voc])
    mod = _INTENT_MODIFIERS.get(intent or "", {})

    base_dur = float(tpl["duration"]) * float(mod.get("duration_scale", 1.0))
    if duration_sec is not None:
        dur_val = float(duration_sec)
        if not np.isfinite(dur_val) or dur_val < 0.08 or dur_val > 6.0:
            raise ValueError("duration_sec must be between 0.08 and 6.0 seconds.")
        target_dur = dur_val
    else:
        target_dur = float(np.clip(base_dur, 0.11, 6.0))

    if intensity is not None:
        int_val = float(intensity)
        if not np.isfinite(int_val) or int_val < 0.15 or int_val > 1.0:
            raise ValueError("intensity must be between 0.15 and 1.0.")
        target_intensity = int_val
    else:
        target_intensity = float(tpl["default_intensity"])

    f0_scale = float(mod.get("f0_scale", 1.0))
    base_f0 = float(tpl["f0_base_hz"]) * f0_scale
    end_f0 = float(tpl["f0_end_hz"]) * f0_scale
    if pitch_hz is not None:
        p_val = float(pitch_hz)
        if not np.isfinite(p_val) or p_val < 60.0 or p_val > 2000.0:
            raise ValueError("pitch_hz must be between 60 and 2000 Hz.")
        ratio = p_val / max(base_f0, 1.0)
        base_f0 = p_val
        end_f0 = float(np.clip(end_f0 * ratio, 60.0, min(2400.0, sr * 0.42)))
    else:
        base_f0 = float(np.clip(base_f0, 60.0, 2000.0))
        end_f0 = float(np.clip(end_f0, 60.0, 2200.0))

    nyq = sr / 2.0
    formant_shift = float(np.clip((base_f0 / float(tpl["f0_base_hz"])) ** 0.25, 0.75, 1.35))
    formants = [round(float(np.clip(f * formant_shift, 150.0, nyq * 0.85)), 1) for f in tpl["formants_hz"]]
    bandwidths = [round(float(bw), 1) for bw in tpl["bandwidths_hz"]]

    n_events = int(mod.get("n_events", tpl["n_events"]))
    if duration_sec is not None and voc in {"bark", "yip", "yelp", "whimper", "grunt", "pant", "soft_attention"}:
        unit = 0.32 if voc == "bark" else 0.24 if voc in {"yip", "yelp"} else 0.36
        n_events = max(1, min(14, int(round(target_dur / unit))))

    seed_key = f"{voc}:{intent or 'none'}:{sr}:{target_dur:.4f}:{base_f0:.2f}:{target_intensity:.3f}"
    seed = int.from_bytes(hashlib.sha256(seed_key.encode("utf-8")).digest()[:4], "little")

    return {
        "profile_id": f"{voc}_{intent}" if intent else voc,
        "vocalization": voc,
        "description": tpl["description"],
        "intent": intent,
        "sr": sr,
        "duration": round(target_dur, 4),
        "f0": round(base_f0, 2),
        "f0_base_hz": round(base_f0, 2),
        "f0_end_hz": round(end_f0, 2),
        "f0_trajectory": tpl["f0_trajectory"],
        "harmonics": int(tpl["harmonics"]),
        "harmonic_rolloff_db": float(tpl["harmonic_rolloff_db"]),
        "formants": formants,
        "formants_hz": formants,
        "bandwidths_hz": bandwidths,
        "noise": float(tpl["noise_ratio"]),
        "noise_ratio": float(tpl["noise_ratio"]),
        "noise_band_hz": list(tpl["noise_band_hz"]),
        "fm_rate_hz": float(tpl["fm_rate_hz"]),
        "fm_depth_hz": float(tpl["fm_depth_hz"]),
        "am_rate_hz": float(tpl["am_rate_hz"]),
        "am_depth": float(tpl["am_depth"]),
        "adsr": {
            "attack_sec": float(tpl["attack_sec"]),
            "decay_sec": float(tpl["decay_sec"]),
            "sustain_level": float(tpl["sustain_level"]),
            "release_sec": float(tpl["release_sec"]),
        },
        "n_events": n_events,
        "gap_sec": float(tpl["gap_sec"]),
        "intensity": round(target_intensity, 3),
        "requested_duration_sec": duration_sec,
        "requested_pitch_hz": pitch_hz,
        "normalization_ceiling": round(0.88 * target_intensity, 4),
        "seed": seed,
        "synthetic": True,
        "synth_version": SYNTH_MODEL_VERSION,
        "method": "experimental_dsp_parallel_formants_rosenberg_glottal",
    }


def synthesize(
    vocalization: str,
    intent: str | None = None,
    sr: int = TARGET_SR,
    intensity: float | None = None,
    duration_sec: float | None = None,
    pitch_hz: float | None = None,
    variation_index: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Synthesize a deterministic waveform in `experimental_dsp` mode using parallel
    formant resonators and onset-gated aspiration (eliminating breaking-stick crackle).
    """
    eff_pitch = pitch_hz
    eff_dur = duration_sec
    if variation_index > 0:
        tpl = _PROFILE_TEMPLATES.get((vocalization or "bark").strip().lower(), _PROFILE_TEMPLATES["bark"])
        f0_offsets = [1.0, 1.045, 0.96, 1.07, 0.935]
        dur_offsets = [1.0, 0.95, 1.06, 0.92, 1.08]
        if eff_pitch is None:
            eff_pitch = float(np.clip(float(tpl["f0_base_hz"]) * f0_offsets[variation_index % len(f0_offsets)], 60.0, 2000.0))
        if eff_dur is None:
            eff_dur = float(np.clip(float(tpl["duration"]) * dur_offsets[variation_index % len(dur_offsets)], 0.08, 6.0))
    params = calculate_synthesis_parameters(
        vocalization=vocalization,
        intent=intent,
        sr=sr,
        intensity=intensity,
        duration_sec=eff_dur,
        pitch_hz=eff_pitch,
    )
    rng = np.random.default_rng(params["seed"] + int(variation_index) * 7919)
    sr_int = int(params["sr"])
    total_samples = max(int(sr_int * 0.08), int(round(sr_int * float(params["duration"]))))
    n_events = int(params["n_events"])
    gap_sec = float(params["gap_sec"]) if n_events > 1 else 0.0

    if n_events <= 1:
        y = _synthesize_single_event(total_samples, sr_int, params, rng, event_idx=0)
    else:
        gap_samples = int(round(gap_sec * sr_int))
        total_gap = gap_samples * (n_events - 1)
        if total_gap >= int(total_samples * 0.60):
            gap_samples = max(1, int(total_samples * 0.32) // max(1, n_events - 1))
            total_gap = gap_samples * (n_events - 1)
        active_samples = max(n_events, total_samples - total_gap)
        base_ev_len = active_samples // n_events
        pieces: list[np.ndarray] = []
        for idx in range(n_events):
            ev_len = base_ev_len if idx < n_events - 1 else (active_samples - base_ev_len * (n_events - 1))
            ev_wave = _synthesize_single_event(max(16, ev_len), sr_int, params, rng, event_idx=idx)
            pieces.append(ev_wave)
            if idx < n_events - 1 and gap_samples > 0:
                pieces.append(np.zeros(gap_samples, dtype=np.float64))
        y = np.concatenate(pieces)
        if y.size < total_samples:
            y = np.pad(y, (0, total_samples - y.size))
        elif y.size > total_samples:
            y = y[:total_samples]

    # Smooth 8 ms raised-cosine boundary taper
    fade = min(max(12, int(0.008 * sr_int)), y.size // 4)
    if fade > 1:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade) / fade))
        y[:fade] *= ramp
        y[-fade:] *= ramp[::-1]

    y = _normalize_safe(y, ceiling=float(params["normalization_ceiling"]))
    y_f32 = y.astype(np.float32)

    rms = float(np.sqrt(np.mean(y_f32**2))) if y_f32.size else 0.0
    peak = float(np.max(np.abs(y_f32))) if y_f32.size else 0.0
    params.update(
        {
            "duration": float(y_f32.size / sr_int),
            "sample_count": int(y_f32.size),
            "output_rms": round(rms, 5),
            "output_peak": round(peak, 5),
            "crest_factor": round(float(peak / (rms + 1e-12)), 4),
        }
    )
    return y_f32, params


_SHORT_BURST = {"yip": 0.095, "bark": 0.115, "yelp": 0.10}
_MID_BURST = {"grunt": 0.20, "soft_attention": 0.21, "groan": 0.24}
_LONG_BURST = {"growl": 0.52}
_PINK_B = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
_PINK_A = [1.0, -2.494956002, 2.017265875, -0.522189400]


def _burst_plan(voc: str, sr: int, n_samples: int) -> list[tuple[int, int]]:
    """Return (start, length) of discrete percussive bursts separated by silence gaps."""
    if voc in _SHORT_BURST:
        dur, gap = _SHORT_BURST[voc], 0.075
    elif voc in _MID_BURST:
        dur, gap = _MID_BURST[voc], 0.09
    elif voc in _LONG_BURST:
        dur, gap = _LONG_BURST[voc], 0.12
    else:  # whine / howl / whimper / cry / pant: multi-burst contours
        dur, gap = (0.30 if voc in {"whine", "howl"} else 0.16), 0.055
    blen = max(16, min(n_samples, int(round(dur * sr))))
    glen = int(round(gap * sr))
    plan: list[tuple[int, int]] = []
    pos = 0
    while pos + blen <= n_samples:
        plan.append((pos, blen))
        pos += blen + glen
    if not plan:
        plan.append((0, blen))
    return plan


def _rosenberg_pulse(p: np.ndarray, open_frac: float = 0.58, close_frac: float = 0.14) -> np.ndarray:
    """Asymmetric Rosenberg glottal pulse: slow raised-cosine opening, rapid closure."""
    g = np.zeros_like(p)
    o = p < open_frac
    g[o] = 0.5 * (1.0 - np.cos(np.pi * p[o] / open_frac))
    c = (p >= open_frac) & (p < open_frac + close_frac)
    g[c] = np.cos(0.5 * np.pi * (p[c] - open_frac) / close_frac)
    return g


def _two_pole_resonator(x: np.ndarray, sr: int, freq: float, bw: float) -> np.ndarray:
    r = float(np.exp(-np.pi * bw / sr))
    # A pole-only resonator's magnitude peak sits slightly below its pole angle; place the pole so the
    # |H| peak lands exactly on the target formant: cos(theta) = cos(w_peak) * 2r / (1 + r^2).
    w_peak = 2.0 * np.pi * freq / sr
    theta = float(np.arccos(np.clip(np.cos(w_peak) * 2.0 * r / (1.0 + r * r), -1.0, 1.0)))
    return lfilter([1.0 - r], [1.0, -2.0 * r * np.cos(theta), r * r], x)


def _synthesize_single_event(
    n_samples: int,
    sr: int,
    params: dict[str, Any],
    rng: np.random.Generator,
    event_idx: int = 0,
) -> np.ndarray:
    """Percussive mammalian vocalization: Rosenberg glottal pulse + sub-harmonic + pink
    aspiration, filtered through pharyngeal (F1) and oral (F2) 2-pole resonators."""
    out = np.zeros(n_samples, dtype=np.float64)
    voc = str(params["vocalization"])
    f0_start = float(params["f0_base_hz"]) * (1.0 + 0.03 * (event_idx % 3))
    f0_end = float(params["f0_end_hz"]) * (1.0 + 0.02 * (event_idx % 2))
    # Weight/breed proxy: lower fundamentals imply a larger vocal tract (lower formants)
    tract_scale = float(np.clip((float(params["f0_base_hz"]) / 360.0) ** 0.25, 0.80, 1.25))
    f1 = 620.0 * tract_scale
    f2 = 1450.0 * tract_scale
    noise_ratio = float(np.clip(float(params["noise_ratio"]) + 0.08, 0.05, 0.30))

    for b_idx, (start, blen) in enumerate(_burst_plan(voc, sr, n_samples)):
        u = np.linspace(0.0, 1.0, blen)
        t = np.arange(blen) / sr
        # Rapid pitch rise then fall across each burst; successive bursts step slightly
        step = 1.0 + 0.035 * ((b_idx % 3) - 1)
        arch = np.sin(np.pi * np.clip(u * 1.1, 0.0, 1.0))
        f0 = (f0_start + (f0_end - f0_start) * u + 0.18 * f0_start * arch) * step
        f0 = f0 * (1.0 + 0.02 * rng.normal(0.0, 1.0, blen).cumsum() / np.sqrt(np.arange(1, blen + 1)))
        f0 = np.clip(f0, 45.0, sr * 0.2)

        phase = np.cumsum(f0 / sr)
        main = _rosenberg_pulse(phase % 1.0)
        sub = _rosenberg_pulse((0.5 * phase) % 1.0)  # half-frequency vocal fold roughness
        excit = main + 0.45 * sub
        excit = excit - float(np.mean(excit))

        pink = lfilter(_PINK_B, _PINK_A, rng.normal(0.0, 1.0, blen))
        pink = pink / (float(np.std(pink)) + 1e-12)
        excit = excit / (float(np.std(excit)) + 1e-12)
        src = (1.0 - noise_ratio) * excit + noise_ratio * pink * (1.0 + 1.5 * np.exp(-t / 0.02))

        y = _two_pole_resonator(src, sr, f1, 170.0)
        y = _two_pole_resonator(y, sr, f2, 260.0) + 0.35 * _two_pole_resonator(src, sr, f1, 170.0)
        y = y / (float(np.max(np.abs(y))) + 1e-12)
        y = np.tanh(1.8 * y)

        att = max(4, int(0.006 * sr))
        env = np.exp(-3.2 * u) * (0.35 + 0.65 * (1.0 - u))
        env[:att] *= 0.5 * (1.0 - np.cos(np.pi * np.arange(att) / att))
        tail = max(4, int(0.008 * sr))
        env[-tail:] *= np.linspace(1.0, 0.0, tail)
        out[start : start + blen] += y * env
    return out


def _parallel_formants(x: np.ndarray, sr: int, formants: list[float], bws: list[float]) -> np.ndarray:
    weights = [1.0, 0.65, 0.32]
    out = np.zeros_like(x, dtype=np.float64)
    for idx, (f, bw) in enumerate(zip(formants, bws)):
        w = weights[idx] if idx < len(weights) else 0.2
        r = float(np.exp(-np.pi * bw / sr))
        theta = 2.0 * np.pi * f / sr
        a = [1.0, -2.0 * r * np.cos(theta), r * r]
        b = [1.0 - r, 0.0, -(1.0 - r)]
        out += w * lfilter(b, a, x)
    return 0.75 * out + 0.25 * x


def _adsr_envelope(
    n: int,
    sr: int,
    attack_sec: float,
    decay_sec: float,
    sustain_level: float,
    release_sec: float,
) -> np.ndarray:
    if n <= 4:
        return np.ones(n, dtype=np.float64)
    att = max(4, int(round(attack_sec * sr)))
    dec = max(4, int(round(decay_sec * sr)))
    rel = max(4, int(round(release_sec * sr)))
    total_adr = att + dec + rel
    if total_adr >= n:
        scale = (n - 1) / max(1, total_adr)
        att = max(2, int(att * scale))
        dec = max(2, int(dec * scale))
        rel = max(2, n - att - dec)
    sus = max(0, n - att - dec - rel)

    env = np.empty(n, dtype=np.float64)
    env[:att] = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, att)))
    env[att : att + dec] = sustain_level + (1.0 - sustain_level) * (0.5 * (1.0 + np.cos(np.pi * np.linspace(0.0, 1.0, dec))))
    if sus > 0:
        env[att + dec : att + dec + sus] = sustain_level
    rel_start = att + dec + sus
    rel_len = n - rel_start
    if rel_len > 0:
        env[rel_start:] = sustain_level * (0.5 * (1.0 + np.cos(np.pi * np.linspace(0.0, 1.0, rel_len))))
    return env


def _normalize_safe(y: np.ndarray, ceiling: float = 0.85) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    y = y - float(np.mean(y))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak < 1e-12:
        return y
    target_ceiling = float(np.clip(ceiling, 0.12, 0.92))
    return (y / peak) * target_ceiling


def validate_generated_wav(path: Path, expected_sr: int = TARGET_SR) -> dict[str, Any]:
    """Validate an encoded WAV file on disk, including discontinuity and transient checks."""
    if not path.exists() or not path.is_file():
        raise ValueError("Generated WAV file does not exist on disk.")
    raw_bytes = path.read_bytes()
    if len(raw_bytes) <= 44 or raw_bytes[:4] != b"RIFF":
        raise ValueError("Generated file is not a valid RIFF WAV container.")
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    info = sf.info(str(path))
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    if int(sr) != int(expected_sr):
        raise ValueError(f"Generated WAV sample rate mismatch: expected {expected_sr}, got {sr}.")
    if int(info.channels) != 1 or y.ndim != 1:
        raise ValueError(f"Generated WAV channel count must be 1 (got {info.channels}).")
    if y.size == 0 or int(info.frames) != int(y.size):
        raise ValueError("Generated WAV has zero or mismatched sample frames.")
    if not bool(np.isfinite(y).all()):
        raise ValueError("Generated WAV contains non-finite sample values.")

    rms = float(np.sqrt(np.mean(y**2)))
    peak = float(np.max(np.abs(y)))
    clipping_ratio = float(np.mean(np.abs(y) > 0.99))
    if rms < 1e-4 or peak < 1e-3:
        raise ValueError("Generated WAV is accidentally silent.")
    if clipping_ratio > 0.02:
        raise ValueError(f"Generated WAV exceeds clipping limit ({clipping_ratio:.4f}).")

    # Discontinuity and unnatural crackle transient detection
    diffs = np.abs(np.diff(y)) if y.size >= 2 else np.zeros(1, dtype=np.float32)
    max_step = float(np.max(diffs))
    abrupt_jumps = int(np.sum(diffs > max(0.72, peak * 1.25)))
    has_abrupt_discontinuity = bool(abrupt_jumps > 6)

    return {
        "valid": True,
        "sample_rate": int(sr),
        "channels": int(info.channels),
        "sample_count": int(y.size),
        "duration_sec": round(float(y.size / sr), 4),
        "finite_samples": True,
        "non_silent": True,
        "rms": round(rms, 5),
        "peak": round(peak, 5),
        "clipping_ratio": round(clipping_ratio, 6),
        "max_sample_step": round(max_step, 5),
        "abrupt_discontinuity_count": abrupt_jumps,
        "has_abrupt_discontinuity": has_abrupt_discontinuity,
        "file_size_bytes": len(raw_bytes),
        "sha256": sha256,
        "subtype": str(info.subtype),
    }


def _spectral_envelope_and_formants(wave: np.ndarray, sr: int) -> tuple[np.ndarray, float, float]:
    """Compute smoothed log-spectral envelope (<=4000 Hz) and F1/F2 peaks."""
    n_fft = 4096
    x = np.asarray(wave, dtype=np.float64).ravel()
    if x.size == 0 or float(np.max(np.abs(x))) < 1e-10:
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / max(int(sr), 1))
        bins = (freqs >= 60.0) & (freqs <= 4000.0)
        return np.full(int(np.sum(bins)), 1e-6, dtype=np.float64), 0.0, 0.0

    # Peak-normalize so spectral comparison captures shape invariant to gain
    x = x / (float(np.max(np.abs(x))) + 1e-12)
    win = np.hanning(min(len(x), n_fft))
    if len(x) >= n_fft:
        # Average power spectra over overlapping segments when longer than n_fft
        hop = n_fft // 2
        mags = []
        for start in range(0, len(x) - n_fft + 1, hop):
            seg = x[start : start + n_fft] * np.hanning(n_fft)
            mags.append(np.abs(np.fft.rfft(seg, n=n_fft)))
        mag = np.mean(mags, axis=0) if mags else np.abs(np.fft.rfft(x[:n_fft], n=n_fft))
    else:
        seg = x * win
        mag = np.abs(np.fft.rfft(seg, n=n_fft))

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / max(int(sr), 1))
    band_mask = (freqs >= 60.0) & (freqs <= 4000.0)
    band_freqs = freqs[band_mask]
    log_mag = np.log10(mag[band_mask] + 1e-7)

    # Moving-average spectral smoothing to extract vocal-tract formant envelope
    kernel_size = 11
    kernel = np.ones(kernel_size, dtype=np.float64) / kernel_size
    pad = kernel_size // 2
    padded = np.pad(log_mag, (pad, pad), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    env = smoothed - float(np.min(smoothed)) + 1e-6

    f1_mask = (band_freqs >= 250.0) & (band_freqs <= 1050.0)
    f2_mask = (band_freqs >= 1050.0) & (band_freqs <= 2800.0)
    f1_hz = float(band_freqs[f1_mask][int(np.argmax(smoothed[f1_mask]))]) if np.any(f1_mask) else 0.0
    f2_hz = float(band_freqs[f2_mask][int(np.argmax(smoothed[f2_mask]))]) if np.any(f2_mask) else 0.0
    return env, f1_hz, f2_hz


def _estimate_burst_rate(wave: np.ndarray, sr: int) -> tuple[int, float]:
    """Estimate discrete vocal burst count and bursts-per-second cadence."""
    x = np.asarray(wave, dtype=np.float64).ravel()
    sr_safe = max(int(sr), 1)
    dur = max(0.2, float(x.size) / sr_safe)
    if x.size == 0 or float(np.max(np.abs(x))) < 1e-10:
        return 0, 0.0

    frame_len = max(1, int(0.020 * sr_safe))
    hop = max(1, frame_len // 2)
    if x.size < frame_len:
        return 1, round(1.0 / dur, 4)

    rms_vals = [
        float(np.sqrt(np.mean(x[i : i + frame_len] ** 2)))
        for i in range(0, x.size - frame_len + 1, hop)
    ]
    rms = np.asarray(rms_vals, dtype=np.float64)
    thresh = max(float(np.mean(rms)) * 1.25, float(np.max(rms)) * 0.18, 0.01)
    active = rms >= thresh
    min_gap_frames = max(1, int(0.050 / (hop / sr_safe)))

    burst_count = 0
    last_onset = -min_gap_frames - 1
    for idx in range(len(active)):
        if active[idx] and (idx == 0 or not active[idx - 1]):
            if idx - last_onset >= min_gap_frames:
                burst_count += 1
                last_onset = idx
    if burst_count == 0 and float(np.max(rms)) >= 0.01:
        burst_count = 1

    return burst_count, float(burst_count) / dur


def compute_acoustic_similarity_to_reference(
    synth_wave: np.ndarray,
    ref_wave: np.ndarray,
    sr: int = TARGET_SR,
) -> dict[str, Any]:
    """Validate synthesized vocalization against a reference waveform via spectral envelope, formants, and cadence."""
    env_synth, synth_f1, synth_f2 = _spectral_envelope_and_formants(synth_wave, sr)
    env_ref, ref_f1, ref_f2 = _spectral_envelope_and_formants(ref_wave, sr)

    min_len = min(len(env_synth), len(env_ref))
    if min_len == 0:
        cos_sim = 0.0
    else:
        es = env_synth[:min_len]
        er = env_ref[:min_len]
        denom = float(np.linalg.norm(es) * np.linalg.norm(er))
        cos_sim = float(np.clip(np.dot(es, er) / (denom + 1e-12), 0.0, 1.0)) if denom > 0 else 0.0

    delta_f1_hz = round(float(abs(synth_f1 - ref_f1)), 2)
    delta_f2_hz = round(float(abs(synth_f2 - ref_f2)), 2)

    synth_bursts, synth_rate = _estimate_burst_rate(synth_wave, sr)
    ref_bursts, ref_rate = _estimate_burst_rate(ref_wave, sr)
    cadence_match = float(
        np.clip(np.exp(-abs(synth_rate - ref_rate) / max(1.5, ref_rate, synth_rate)), 0.0, 1.0)
    )

    return {
        "log_spectral_cosine_similarity": round(cos_sim, 4),
        "synth_formants_hz": [round(synth_f1, 1), round(synth_f2, 1)],
        "ref_formants_hz": [round(ref_f1, 1), round(ref_f2, 1)],
        "delta_f1_hz": delta_f1_hz,
        "delta_f2_hz": delta_f2_hz,
        "formant_peak_deviation_hz": {
            "delta_f1_hz": delta_f1_hz,
            "delta_f2_hz": delta_f2_hz,
        },
        "synth_burst_count": int(synth_bursts),
        "ref_burst_count": int(ref_bursts),
        "synth_burst_rate_hz": round(synth_rate, 2),
        "ref_burst_rate_hz": round(ref_rate, 2),
        "burst_cadence_match": round(cadence_match, 4),
    }
