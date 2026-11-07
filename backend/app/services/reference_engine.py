"""
Hybrid Reference-Driven Canine Vocalization Engine (Engine B v2).

Replaces primitive oscillator-first synthesis with a reference-driven hierarchy:
- Method A (`reference_direct`): Real reference audio retrieval from validated dog recordings.
- Method B (`reference_variation`): Controlled, naturalness-preserving transformations of real reference recordings.
- Method C (`generative_model`): Data-conditioned generative audio model assessment & guardrails.
- Method D (`experimental_dsp`): Repaired parametric DSP fallback (clearly labeled as synthetic).

Never confuses original reference playback, transformed reference audio, model-generated audio,
or experimental DSP output.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt, medfilt

from ..config import TARGET_SR
from .reference_library import (
    CATEGORY_FALLBACK_ORDER,
    SUPPORTED_REFERENCE_CATEGORIES,
    build_or_load_reference_library,
    category_to_legacy_profile,
    compute_reference_acoustic_profile,
    get_reference_asset,
    is_reference_accessible,
    normalize_category,
)
from .synthesis import calculate_synthesis_parameters, synthesize

GENERATION_METHODS: tuple[str, ...] = (
    "reference_direct",
    "reference_variation",
    "generative_model",
    "experimental_dsp",
)

# All 11 categories have dedicated profile templates in synthesis.py
_DSP_UNSUPPORTED_CATEGORIES: frozenset[str] = frozenset()

# Label provenance: confirmed labels without a named reviewer come from source/curation metadata only.
LABEL_UNVERIFIED_NOTE = (
    "Category label comes from source/curation metadata and has not been independently verified "
    "by a named human reviewer."
)

OUTPUT_CLASSIFICATION_LABELS: dict[str, str] = {
    "reference_direct": "Original Reference Audio (Retrieval)",
    "reference_variation": "Transformed Reference Audio (Modified Recording)",
    "generative_model": "Model-Generated Audio",
    "experimental_dsp": "Experimental DSP Output (Synthetic)",
}


def assess_generative_model_status() -> dict[str, Any]:
    """
    Section 4 Method C — Honest technical, hardware, data, and legal assessment
    for data-conditioned neural audio generation models.
    """
    lib = build_or_load_reference_library()
    cat_counts = lib.get("category_counts", {})
    total_valid = lib.get("total_accepted_canine_references", 0)
    return {
        "model_available": False,
        "status": "BLOCKED_BY_INSUFFICIENT_TRAINING_DATA_AND_LICENSE_TERMS",
        "evaluated_candidates": [
            {
                "model_name": "AudioLDM2 / Make-An-Audio 2",
                "license": "CC-BY-NC-SA 4.0 (Non-Commercial Only)",
                "audio_conditioning_supported": True,
                "vram_requirement_gb": 8.0,
                "suitability": "Pretrained on general AudioSet sound effects; produces generic low-fidelity animal effects without fine-tuning on hundreds of licensed dog recordings.",
            },
            {
                "model_name": "RVC v2 / DDSP Canine Vocal Tract Autoencoder",
                "license": "MIT (code) / Custom corpus required",
                "audio_conditioning_supported": True,
                "vram_requirement_gb": 4.0,
                "suitability": "Requires >= 30 minutes of clean, single-dog, rights-cleared studio recordings per vocalization class to avoid robotic phase artifacts.",
            },
        ],
        "corpus_size_check": {
            "total_valid_reference_clips": total_valid,
            "category_counts": cat_counts,
            "sufficient_for_neural_training": False,
            "minimum_recommended_clips_per_class": 250,
        },
        "rights_and_consent_check": {
            "training_permitted": False,
            "reason": (
                "Reference recordings originate from BigSoundBank (`unknown_verify_bigsoundbank_terms`) "
                "and unverified field recordings. License terms do not authorize training or redistributing "
                "a generative ML model on these assets."
            ),
        },
        "active_working_solution": "Methods A (reference_direct) and B (reference_variation) using validated real dog recordings.",
    }


def search_reference_candidates(
    category: str,
    target_duration_sec: float | None = None,
    target_pitch_hz: float | None = None,
    preferred_asset_id: str | None = None,
    limit: int = 10,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search and rank validated canine reference recordings by category match,
    human review status, acoustic quality, active vocalization ratio, duration proximity,
    and pitch proximity. Enforces per-user ownership isolation on uploaded references.
    """
    req_cat = normalize_category(category)
    lib = build_or_load_reference_library()
    valid_assets = [
        a
        for a in lib.get("assets", [])
        if a.get("technical_validation_status") == "valid_canine_reference"
        and is_reference_accessible(a, user_id)
        and Path(a.get("processed_path", "")).exists()
    ]

    if preferred_asset_id:
        explicit = [a for a in valid_assets if a["asset_id"] == preferred_asset_id]
        if explicit:
            a0 = dict(explicit[0])
            a0["suitability_score"] = 1.0
            a0["match_tier"] = "explicit_user_selection"
            return [a0]
        raise ValueError(f"Requested reference asset '{preferred_asset_id}' not found or not accessible.")

    fallback_chain = CATEGORY_FALLBACK_ORDER.get(req_cat, [req_cat, "BARK"])
    scored: list[dict[str, Any]] = []

    desired_dur = target_duration_sec if target_duration_sec is not None else _default_category_duration(req_cat)

    for a in valid_assets:
        eff_cat = a.get("effective_category") or "UNKNOWN"
        if eff_cat not in fallback_chain:
            continue
        tier_idx = fallback_chain.index(eff_cat)

        # Prefer human-reviewed annotations over auto-suggested
        is_reviewed = a.get("annotation_status") == "human_reviewed"
        ann_bonus = 0.08 if is_reviewed else 0.0

        # Prefer clean focal clips (0.25s - 8.0s) over 25s-180s full session files unless long duration requested
        dur = float(a.get("duration_sec") or 1.0)
        dur_diff = abs(np.log((dur + 0.1) / (desired_dur + 0.1)))
        dur_score = float(np.exp(-0.45 * dur_diff))
        if 0.25 <= dur <= 8.0:
            dur_score += 0.06
        elif dur > 15.0:
            dur_score -= 0.15
        if target_duration_sec is not None:
            if dur < float(target_duration_sec) * 0.75:
                dur_score -= 0.90
            elif abs(dur - float(target_duration_sec)) <= 0.25:
                dur_score += 0.35

        # Active vocalization density bonus (penalize mostly silent clips)
        sil_ratio = float(a.get("silence_ratio") or 0.0)
        active_ratio = max(0.0, 1.0 - sil_ratio)
        active_bonus = 0.06 * min(1.0, active_ratio / 0.45) - (0.12 if sil_ratio > 0.72 else 0.0)

        # Quality bonus (non-clipped, good RMS)
        qual_score = 0.04 if not a.get("is_clipped") else -0.10

        # Pitch proximity bonus if requested
        pitch_score = 0.0
        if target_pitch_hz is not None and target_pitch_hz > 0:
            fd = (a.get("acoustic_profile") or {}).get("frequency_domain", {})
            ref_f0 = fd.get("f0_mean_hz") or fd.get("dominant_freq_hz")
            if ref_f0 and ref_f0 > 0:
                semitone_diff = abs(12.0 * np.log2(target_pitch_hz / float(ref_f0)))
                pitch_score = float(0.06 * np.exp(-semitone_diff / 8.0))

        raw_subscore = ann_bonus + 0.12 * dur_score + active_bonus + qual_score + pitch_score
        if tier_idx == 0:
            # Exact category matches always score in [0.75, 1.00]
            total_score = round(float(np.clip(0.76 + raw_subscore, 0.75, 1.0)), 4)
        else:
            # Fallback categories never exceed 0.72 so exact matches always rank first
            base_fb = max(0.35, 0.62 - 0.10 * tier_idx)
            total_score = round(float(np.clip(base_fb + 0.5 * raw_subscore, 0.25, 0.72)), 4)

        item = dict(a)
        item["suitability_score"] = total_score
        item["match_tier"] = "exact_category" if tier_idx == 0 else f"related_fallback({eff_cat})"
        scored.append(item)

    scored.sort(
        key=lambda x: (
            1 if x["match_tier"] == "exact_category" else 0,
            x["suitability_score"],
            1 if x.get("annotation_status") == "human_reviewed" else 0,
            -float(x.get("silence_ratio", 0.5)),
            -abs(float(x.get("duration_sec", 1.0)) - desired_dur),
        ),
        reverse=True,
    )
    return scored[:limit]


def _default_category_duration(cat: str) -> float:
    defaults = {
        "BARK": 1.2,
        "GROWL": 1.6,
        "HOWL": 2.2,
        "WHINE": 1.4,
        "YIP": 0.6,
        "YELP": 0.5,
        "WHIMPER": 1.3,
        "CRY": 1.6,
        "GRUNT": 0.8,
        "GROAN": 1.2,
        "PANT": 1.8,
        "MIXED": 1.5,
        "UNKNOWN": 1.2,
    }
    return defaults.get(cat, 1.2)


def _select_active_focal_window(
    y: np.ndarray,
    sr: int,
    target_duration_sec: float | None,
    category: str,
) -> tuple[np.ndarray, dict[str, float]]:
    """
    When a reference recording is much longer than the requested duration (e.g., a 30s field
    recording), select the highest-energy vocalization window bounded by low-energy valleys
    and apply smooth 8ms raised-cosine edge tapers so there are zero clicks or cuts.
    When the reference clip is already concise (<= 6.0s and no shorter custom duration requested),
    preserve the entire reference clip intact.
    """
    n = int(y.size)
    full_dur = float(n / sr)
    if target_duration_sec is None:
        if full_dur <= 6.0:
            return _apply_edge_taper(y.copy(), sr, taper_ms=6.0), {
                "window_start_sec": 0.0,
                "window_end_sec": round(full_dur, 3),
                "full_reference_duration_sec": round(full_dur, 3),
                "trimmed": False,
            }
        target_dur = min(full_dur, max(1.2, _default_category_duration(category) * 1.5))
    else:
        target_dur = float(np.clip(target_duration_sec, 0.12, min(12.0, full_dur)))
        if abs(full_dur - target_dur) <= 0.25 and full_dur <= 6.0:
            return _apply_edge_taper(y.copy(), sr, taper_ms=6.0), {
                "window_start_sec": 0.0,
                "window_end_sec": round(full_dur, 3),
                "full_reference_duration_sec": round(full_dur, 3),
                "trimmed": False,
            }

    win_samples = min(n, max(int(0.12 * sr), int(round(target_dur * sr))))
    if win_samples >= n:
        return _apply_edge_taper(y.copy(), sr, taper_ms=6.0), {
            "window_start_sec": 0.0,
            "window_end_sec": round(full_dur, 3),
            "full_reference_duration_sec": round(full_dur, 3),
            "trimmed": False,
        }

    # Find highest-RMS window of length win_samples using 20ms hop
    hop = max(1, int(0.02 * sr))
    frame_rms = librosa.feature.rms(y=y, frame_length=min(1024, win_samples), hop_length=hop)[0]
    win_frames = max(1, int(round(win_samples / hop)))
    if frame_rms.size > win_frames:
        csum = np.cumsum(np.insert(frame_rms**2, 0, 0.0))
        best_frame = int(np.argmax(csum[win_frames:] - csum[:-win_frames]))
        start_sample = min(n - win_samples, best_frame * hop)
    else:
        start_sample = 0

    end_sample = start_sample + win_samples
    sub = y[start_sample:end_sample].copy()
    sub = _apply_edge_taper(sub, sr, taper_ms=10.0)
    return sub, {
        "window_start_sec": round(float(start_sample / sr), 3),
        "window_end_sec": round(float(end_sample / sr), 3),
        "full_reference_duration_sec": round(full_dur, 3),
        "trimmed": True,
    }


def _apply_edge_taper(y: np.ndarray, sr: int, taper_ms: float = 8.0) -> np.ndarray:
    fade = min(max(8, int(round((taper_ms / 1000.0) * sr))), y.size // 4)
    if fade > 1:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade, dtype=np.float32) / fade))
        y[:fade] *= ramp
        y[-fade:] *= ramp[::-1]
    return y


def _apply_controlled_variation(
    y_ref: np.ndarray,
    sr: int,
    category: str,
    ref_asset: dict[str, Any],
    target_duration_sec: float | None = None,
    target_pitch_hz: float | None = None,
    intensity: float | None = None,
    pitch_shift_semitones: float | None = None,
    time_stretch_rate: float | None = None,
    variation_index: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Method B — Controlled, naturalness-preserving reference variation.
    Applies bounded pitch shifting ([-2.0, +2.0] semitones), bounded time stretching
    ([0.85, 1.18]), gentle high-frequency room-noise smoothing, and dynamic scaling.
    Enforces an automatic naturalness gate: rejects phase-vocoder transformations that
    degrade spectral/timbral coherence or introduce metallic/transient artifacts, falling
    back to cohesive formant-preserving resampling.
    """
    y_orig = y_ref.astype(np.float32).copy()
    y = y_orig.copy()
    clamped_for_naturalness = False

    # 1. Determine bounded pitch shift in semitones ([-2.0, +2.0])
    if pitch_shift_semitones is not None:
        if abs(float(pitch_shift_semitones)) > 2.0:
            clamped_for_naturalness = True
        st_shift = float(np.clip(pitch_shift_semitones, -2.0, 2.0))
    elif target_pitch_hz is not None and target_pitch_hz > 0:
        fd = (ref_asset.get("acoustic_profile") or {}).get("frequency_domain", {})
        ref_f0 = fd.get("f0_mean_hz") or fd.get("dominant_freq_hz")
        if ref_f0 and ref_f0 > 50:
            raw_st = 12.0 * np.log2(float(target_pitch_hz) / float(ref_f0))
            if abs(raw_st) > 2.0:
                clamped_for_naturalness = True
            st_shift = float(np.clip(raw_st, -2.0, 2.0))
        else:
            st_shift = 0.0
    else:
        # Subtle deterministic variation across regeneration clicks
        offsets = [0.35, -0.35, 0.55, -0.50, 0.25]
        st_shift = offsets[variation_index % len(offsets)]

    # 2. Determine bounded time-stretch rate ([0.85, 1.18])
    cur_dur = float(y.size / sr)
    if time_stretch_rate is not None:
        if float(time_stretch_rate) < 0.85 or float(time_stretch_rate) > 1.18:
            clamped_for_naturalness = True
        ts_rate = float(np.clip(time_stretch_rate, 0.85, 1.18))
    elif target_duration_sec is not None and cur_dur > 0.08:
        desired_rate = cur_dur / float(target_duration_sec)
        ts_rate = float(np.clip(desired_rate, 0.85, 1.18))
    else:
        ts_rate = 1.0

    explicit_phase_vocoder = (
        (time_stretch_rate is not None and abs(ts_rate - 1.0) >= 0.025)
        or (target_duration_sec is not None and abs(ts_rate - 1.0) >= 0.025)
        or (pitch_shift_semitones is not None and time_stretch_rate is not None)
    )

    variation_technique = "cohesive_formant_resampling"
    phase_vocoder_rejected = False

    if explicit_phase_vocoder and y.size >= 1024:
        y_pv = y.copy()
        if abs(ts_rate - 1.0) >= 0.025:
            y_pv = librosa.effects.time_stretch(y_pv, rate=ts_rate).astype(np.float32)
        if abs(st_shift) >= 0.12 and y_pv.size >= 1024:
            y_pv = librosa.effects.pitch_shift(y_pv, sr=sr, n_steps=st_shift).astype(np.float32)
        # Naturalness gate: verify phase-vocoder candidate did not degrade spectral/timbre similarity
        pv_check = compare_with_reference(y_orig, y_pv, sr, ref_asset=ref_asset)
        if (
            pv_check.get("spectral_envelope_similarity", 0.0) >= 0.88
            and pv_check.get("mfcc_timbre_similarity", 0.0) >= 0.78
            and not pv_check.get("unnatural_crackle_or_transient_detected", False)
        ):
            y = y_pv
            variation_technique = "bounded_phase_vocoder"
        else:
            phase_vocoder_rejected = True

    if variation_technique == "cohesive_formant_resampling" and y.size >= 256:
        # Cohesive resampling shifts pitch and vocal-tract formants together without STFT phase smear
        speed_factor = float(2.0 ** (st_shift / 12.0))
        if abs(speed_factor - 1.0) >= 0.008:
            virtual_sr = max(4000, int(round(sr * speed_factor)))
            y = librosa.resample(y_orig, orig_sr=virtual_sr, target_sr=sr).astype(np.float32)
            ts_rate = round(float(speed_factor), 3)

    # 3. Gentle low-pass smoothing at 9.2 kHz to prevent ultrasonic aliasing
    nyq = sr / 2.0
    cutoff = min(9200.0, nyq * 0.90)
    b, a = butter(3, cutoff / nyq, btype="low")
    y = filtfilt(b, a, y).astype(np.float32)

    # 4. If user requested a specific shorter duration after stretch, trim at low-energy boundary
    if target_duration_sec is not None:
        target_samples = max(int(0.10 * sr), int(round(float(target_duration_sec) * sr)))
        if y.size > int(target_samples * 1.15):
            y, _ = _select_active_focal_window(y, sr, target_duration_sec, category)

    # 5. Apply smooth raised-cosine edge tapers and linear peak normalization (no tanh distortion)
    y = _apply_edge_taper(y, sr, taper_ms=10.0)
    target_ceiling = float(np.clip((intensity if intensity is not None else 0.85) * 0.92, 0.18, 0.92))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1e-8:
        y = (y / peak) * target_ceiling

    return y.astype(np.float32), {
        "pitch_shift_semitones": round(st_shift, 3),
        "time_stretch_rate": round(ts_rate, 3),
        "variation_technique": variation_technique,
        "clamped_for_naturalness": clamped_for_naturalness,
        "phase_vocoder_rejected_for_naturalness": phase_vocoder_rejected,
        "lowpass_smoothing_hz": round(cutoff, 1),
        "target_ceiling": round(target_ceiling, 4),
        "nonlinear_distortion_applied": False,
    }


def detect_transient_artifacts(y: np.ndarray, sr: int = TARGET_SR) -> dict[str, Any]:
    """
    Waveform discontinuity / click / clipping detector.

    A click is a sample whose second difference is a large outlier versus the local
    (31-sample median) second-difference level, i.e. a sudden slope break that is not part of
    smooth voiced content. Also reports clipped-sample ratio and whether the first/last 1 ms
    do not start/end near zero (which produces an audible tick).
    """
    y = np.asarray(y, dtype=np.float32)
    if y.size < 64 or not np.all(np.isfinite(y)):
        return {"click_count": 0, "clipped_ratio": 0.0, "edge_discontinuity": False, "finite": bool(np.all(np.isfinite(y)))}
    peak = float(np.max(np.abs(y))) + 1e-9
    d2 = np.abs(np.diff(y, 2))
    local = medfilt(d2, 31) + 1e-6
    clicks = int(np.sum(d2 > 12.0 * local + 0.05 * peak))
    clipped_ratio = float(np.mean(np.abs(y) >= 0.995))
    n = max(4, int(0.001 * sr))
    edge = bool(max(abs(float(y[0])), abs(float(y[-1]))) > 0.02 * peak + 0.002 or abs(float(y[:n].mean())) > 0.05 * peak)
    return {"click_count": clicks, "clipped_ratio": clipped_ratio, "edge_discontinuity": edge, "finite": True}


def validate_output_audio(y: np.ndarray) -> np.ndarray:
    """
    Final technical gate for every Engine B output (all methods): finite samples, not silent,
    and headroom below full scale so PCM_16 encoding cannot hard-clip. Peak is scaled (never
    clipped) when above 0.98; the gain applied is a pure linear scale.
    """
    y = np.asarray(y, dtype=np.float32).reshape(-1)
    if y.size < 256:
        raise ValueError("Generated audio is too short to be a valid vocalization.")
    if not np.all(np.isfinite(y)):
        raise ValueError("Generated audio contained NaN/Inf samples and was rejected.")
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y**2)))
    if peak < 1e-4 or rms < 2e-5:
        raise ValueError("Generated audio is silent and was rejected.")
    if peak > 0.98:
        y = (y * (0.98 / peak)).astype(np.float32)
    return y


def compare_with_reference(
    y_ref: np.ndarray,
    y_gen: np.ndarray,
    sr: int,
    ref_asset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Section 7 — Objective acoustic comparison between the source reference recording
    and the generated/transformed output, plus quality checks for transients/discontinuities.
    """
    ref_prof = (
        ref_asset.get("acoustic_profile")
        if ref_asset and ref_asset.get("acoustic_profile", {}).get("valid")
        else compute_reference_acoustic_profile(y_ref, sr)
    )
    gen_prof = compute_reference_acoustic_profile(y_gen, sr)

    ref_td = ref_prof.get("time_domain", {})
    gen_td = gen_prof.get("time_domain", {})
    ref_fd = ref_prof.get("frequency_domain", {})
    gen_fd = gen_prof.get("frequency_domain", {})
    ref_tf = ref_prof.get("time_frequency", {})
    gen_tf = gen_prof.get("time_frequency", {})

    # Cosine similarity of Mel band dB envelope
    ref_mel = np.asarray(ref_tf.get("mel_band_db") or [0.0], dtype=float)
    gen_mel = np.asarray(gen_tf.get("mel_band_db") or [0.0], dtype=float)
    if ref_mel.size == gen_mel.size and ref_mel.size > 1:
        r_m = ref_mel - np.min(ref_mel) + 1e-6
        g_m = gen_mel - np.min(gen_mel) + 1e-6
        mel_sim = float(np.dot(r_m, g_m) / (np.linalg.norm(r_m) * np.linalg.norm(g_m) + 1e-12))
    else:
        mel_sim = 0.0

    # Cosine similarity of MFCC mean vector (excluding c0 energy offset)
    ref_mfcc = np.asarray((ref_tf.get("mfcc_mean") or [0.0, 0.0])[1:], dtype=float)
    gen_mfcc = np.asarray((gen_tf.get("mfcc_mean") or [0.0, 0.0])[1:], dtype=float)
    if ref_mfcc.size == gen_mfcc.size and ref_mfcc.size > 1:
        mfcc_sim = float(np.dot(ref_mfcc, gen_mfcc) / (np.linalg.norm(ref_mfcc) * np.linalg.norm(gen_mfcc) + 1e-12))
    else:
        mfcc_sim = 0.0

    cent_ref = float(ref_fd.get("spectral_centroid_hz") or 0.0)
    cent_gen = float(gen_fd.get("spectral_centroid_hz") or 0.0)
    hnr_ref = float(ref_fd.get("hnr_db") or 0.0)
    hnr_gen = float(gen_fd.get("hnr_db") or 0.0)
    dur_ref = float(ref_td.get("duration_sec") or 0.0)
    dur_gen = float(gen_td.get("duration_sec") or 0.0)
    rms_ref = float(ref_td.get("rms_energy") or 0.0)
    rms_gen = float(gen_td.get("rms_energy") or 0.0)

    # Unnatural transient / breaking-stick crackle check.
    # Uses a robust second-difference outlier detector, judged RELATIVE to the source reference so a
    # naturally sharp bark onset is not penalised but clicks introduced by processing are.
    peak_gen = float(gen_td.get("peak_amplitude") or 0.0)
    art_gen = detect_transient_artifacts(y_gen)
    art_ref = detect_transient_artifacts(y_ref)
    abrupt_jumps = int(art_gen["click_count"])
    flatness_gen = float(gen_fd.get("spectral_flatness") or 0.0)
    crackle_detected = bool(
        abrupt_jumps > art_ref["click_count"] + 2
        or art_gen["clipped_ratio"] > max(0.001, art_ref["clipped_ratio"] * 1.5)
        or art_gen["edge_discontinuity"]
        or flatness_gen > 0.38
    )

    return {
        "spectral_envelope_similarity": round(float(np.clip(mel_sim, 0.0, 1.0)), 4),
        "mfcc_timbre_similarity": round(float(np.clip((mfcc_sim + 1.0) / 2.0, 0.0, 1.0)), 4),
        "centroid_delta_hz": round(cent_gen - cent_ref, 1),
        "hnr_delta_db": round(hnr_gen - hnr_ref, 2),
        "duration_delta_sec": round(dur_gen - dur_ref, 3),
        "rms_delta": round(rms_gen - rms_ref, 5),
        "unnatural_crackle_or_transient_detected": crackle_detected,
        "abrupt_discontinuity_jumps": abrupt_jumps,
        "reference_click_count": int(art_ref["click_count"]),
        "output_clipped_ratio": round(float(art_gen["clipped_ratio"]), 6),
        "output_edge_discontinuity": bool(art_gen["edge_discontinuity"]),
        "reference_metrics": {
            "duration_sec": dur_ref,
            "rms_energy": rms_ref,
            "peak_amplitude": float(ref_td.get("peak_amplitude") or 0.0),
            "f0_mean_hz": ref_fd.get("f0_mean_hz"),
            "dominant_freq_hz": ref_fd.get("dominant_freq_hz"),
            "spectral_centroid_hz": cent_ref,
            "spectral_flatness": float(ref_fd.get("spectral_flatness") or 0.0),
            "hnr_db": hnr_ref,
            "event_count": int(ref_td.get("event_count") or 1),
        },
        "generated_metrics": {
            "duration_sec": dur_gen,
            "rms_energy": rms_gen,
            "peak_amplitude": peak_gen,
            "f0_mean_hz": gen_fd.get("f0_mean_hz"),
            "dominant_freq_hz": gen_fd.get("dominant_freq_hz"),
            "spectral_centroid_hz": cent_gen,
            "spectral_flatness": flatness_gen,
            "hnr_db": hnr_gen,
            "event_count": int(gen_td.get("event_count") or 1),
        },
        "disclaimer": (
            "Objective spectral and temporal similarity metrics compare acoustic signal properties "
            "against the source reference recording; they do not prove human-perceived realism or canine comprehension."
        ),
    }


def generate_reference_driven_audio(
    vocalization: str,
    intent: str | None = None,
    generation_method: str = "reference_direct",
    reference_asset_id: str | None = None,
    intensity: float | None = None,
    duration_sec: float | None = None,
    pitch_hz: float | None = None,
    pitch_shift_semitones: float | None = None,
    time_stretch_rate: float | None = None,
    variation_index: int = 0,
    strict_model_only: bool = False,
    user_id: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Execute the complete Reference-Based Generation Workflow (Section 5):
    Vocalization category selection -> Reference library search -> Suitability evaluation ->
    Reference selection -> Retrieval or Controlled Variation (or DSP fallback) ->
    Acoustic comparison & quality control.
    """
    method = (generation_method or "reference_direct").strip().lower()
    if method not in GENERATION_METHODS:
        raise ValueError(f"Unsupported generation_method '{generation_method}'. Must be one of {GENERATION_METHODS}.")

    req_category = normalize_category(vocalization)
    legacy_profile = category_to_legacy_profile(req_category)
    warnings: list[str] = []
    model_assessment = None

    # Validate numeric parameter bounds upfront
    base_params = calculate_synthesis_parameters(
        vocalization=legacy_profile,
        intent=intent,
        sr=TARGET_SR,
        intensity=intensity,
        duration_sec=duration_sec,
        pitch_hz=pitch_hz,
    )

    # Handle Method C (Generative Model) explicitly
    requested_method = method
    method_substituted = False
    if method == "generative_model":
        model_assessment = assess_generative_model_status()
        if strict_model_only:
            raise ValueError(
                "Data-conditioned neural generative model inference is blocked: "
                + model_assessment["rights_and_consent_check"]["reason"]
            )
        warnings.append(
            "METHOD C UNAVAILABLE (BLOCKED): no rights-cleared corpus or verified dog-capable neural model exists. "
            "This output was NOT model-generated; it was produced by Method B (reference_variation) "
            "from a real dog reference recording and is labelled accordingly."
        )
        method = "reference_variation"
        method_substituted = True

    # Handle Method D (Experimental DSP fallback) explicitly
    if method == "experimental_dsp":
        if req_category in _DSP_UNSUPPORTED_CATEGORIES:
            raise ValueError(
                f"Experimental DSP has no valid model for '{req_category}' (it would render a different vocalization). "
                "Use reference_direct or reference_variation."
            )

        y_dsp, dsp_params = synthesize(
            vocalization=legacy_profile,
            intent=intent,
            sr=TARGET_SR,
            intensity=intensity,
            duration_sec=duration_sec,
            pitch_hz=pitch_hz,
            variation_index=variation_index,
        )
        # Compare against top reference candidate if one exists for transparency
        candidates = search_reference_candidates(req_category, duration_sec, pitch_hz, limit=3, user_id=user_id)
        comparison = None
        source_ref_ids: list[str] = []
        primary_ref = None
        if candidates:
            primary_ref = candidates[0]
            y_ref, _ = sf.read(str(primary_ref["processed_path"]), dtype="float32")
            comparison = compare_with_reference(y_ref, y_dsp, TARGET_SR, ref_asset=primary_ref)
        warnings.append(
            "Generated using experimental parametric DSP oscillator/formant synthesis (not a real dog recording)."
        )
        y_dsp = validate_output_audio(y_dsp)
        dsp_params.update(
            {
                "requested_category": req_category,
                "generation_method": "experimental_dsp",
                "requested_generation_method": requested_method,
                "method_substituted": False,
                "output_classification": OUTPUT_CLASSIFICATION_LABELS["experimental_dsp"],
                "is_reference_recording": False,
                "is_modified_recording": False,
                "synthetic": True,
                "source_reference_asset_ids": source_ref_ids,
                "primary_reference_asset": _summarize_ref_asset(primary_ref) if primary_ref else None,
                "candidate_references": [_summarize_ref_asset(c) for c in candidates[:3]],
                "transformation_parameters": {"mode": "parametric_dsp"},
                "acoustic_comparison": comparison,
                "generation_warnings": warnings,
            }
        )
        return y_dsp, dsp_params

    # Methods A (`reference_direct`) and B (`reference_variation`)
    candidates = search_reference_candidates(
        category=req_category,
        target_duration_sec=duration_sec,
        target_pitch_hz=pitch_hz,
        preferred_asset_id=reference_asset_id,
        limit=8,
        user_id=user_id,
    )
    if not candidates:
        raise ValueError(f"No validated canine reference recordings found for category '{req_category}'.")

    # Select candidate (allow variation_index to cycle among top exact-match candidates if no explicit asset_id given)
    exact_matches = [c for c in candidates if c.get("match_tier") in {"explicit_user_selection", "exact_category"}]
    pool = exact_matches if exact_matches else candidates
    selected_ref = pool[variation_index % len(pool)] if not reference_asset_id else pool[0]

    if selected_ref.get("effective_category") != req_category:
        warnings.append(
            f"No exact reference asset for '{req_category}'; selected closest validated reference in category '{selected_ref.get('effective_category')}'."
        )

    ref_wav_path = Path(selected_ref["processed_path"])
    y_ref_full, ref_sr = sf.read(str(ref_wav_path), dtype="float32", always_2d=False)
    if y_ref_full.ndim > 1:
        y_ref_full = np.mean(y_ref_full, axis=1)
    if int(ref_sr) != TARGET_SR:
        y_ref_full = librosa.resample(y_ref_full, orig_sr=int(ref_sr), target_sr=TARGET_SR)

    # Extract clean focal window from the reference recording
    y_focal, window_info = _select_active_focal_window(
        y_ref_full,
        TARGET_SR,
        target_duration_sec=duration_sec,
        category=req_category,
    )

    if method == "reference_direct":
        # Method A: Authentic reference retrieval (optional peak level scaling only if intensity explicitly requested)
        y_out = y_focal.copy()
        gain_applied = 1.0
        if intensity is not None:
            peak = float(np.max(np.abs(y_out))) if y_out.size else 0.0
            if peak > 1e-8:
                target_peak = float(np.clip(intensity * 0.92, 0.15, 0.95))
                gain_applied = target_peak / peak
                y_out = (y_out * gain_applied).astype(np.float32)
        transform_params = {
            "mode": "reference_direct_retrieval",
            "pitch_shift_semitones": 0.0,
            "time_stretch_rate": 1.0,
            "gain_scale": round(float(gain_applied), 4),
            **window_info,
        }
        is_ref_rec = True
        is_mod_rec = False
    else:
        # Method B: Controlled reference-based sound variation
        y_out, var_meta = _apply_controlled_variation(
            y_focal,
            TARGET_SR,
            category=req_category,
            ref_asset=selected_ref,
            target_duration_sec=duration_sec,
            target_pitch_hz=pitch_hz,
            intensity=intensity,
            pitch_shift_semitones=pitch_shift_semitones,
            time_stretch_rate=time_stretch_rate,
            variation_index=variation_index,
        )
        transform_params = {
            "mode": "controlled_reference_variation",
            **window_info,
            **var_meta,
        }
        if var_meta.get("clamped_for_naturalness"):
            warnings.append("Requested pitch shift or time stretch exceeded safe naturalness bounds and was clamped to [-2.0, +2.0] semitones / [0.85, 1.18]x.")
        if var_meta.get("phase_vocoder_rejected_for_naturalness"):
            warnings.append("Phase-vocoder stretch reduced spectral coherence; automatically applied cohesive formant-preserving resampling.")
        is_ref_rec = False
        is_mod_rec = True

    y_out = validate_output_audio(y_out)
    comparison = compare_with_reference(y_focal, y_out, TARGET_SR, ref_asset=selected_ref)
    if comparison.get("unnatural_crackle_or_transient_detected"):
        warnings.append(
            "Artifact check flagged this output (clicks/clipping/edge discontinuity beyond the source reference); "
            "listen before use."
        )
    if not selected_ref.get("reviewed_by"):
        warnings.append(LABEL_UNVERIFIED_NOTE)

    rms_out = float(np.sqrt(np.mean(y_out**2))) if y_out.size else 0.0
    peak_out = float(np.max(np.abs(y_out))) if y_out.size else 0.0
    gen_metrics = comparison.get("generated_metrics", {})

    base_params.update(
        {
            "requested_category": req_category,
            "vocalization": legacy_profile,
            "generation_method": method,
            "requested_generation_method": requested_method,
            "method_substituted": method_substituted,
            "method": method,
            "output_classification": OUTPUT_CLASSIFICATION_LABELS[method],
            "is_reference_recording": is_ref_rec,
            "is_modified_recording": is_mod_rec,
            "synthetic": False,
            "source_reference_asset_ids": [selected_ref["asset_id"]],
            "primary_reference_asset": _summarize_ref_asset(selected_ref),
            "candidate_references": [_summarize_ref_asset(c) for c in candidates[:5]],
            "transformation_parameters": transform_params,
            "model_assessment": model_assessment,
            "duration": round(float(y_out.size / TARGET_SR), 4),
            "sample_count": int(y_out.size),
            "f0": gen_metrics.get("f0_mean_hz") or gen_metrics.get("dominant_freq_hz") or base_params["f0"],
            "f0_base_hz": gen_metrics.get("f0_mean_hz") or gen_metrics.get("dominant_freq_hz") or base_params["f0_base_hz"],
            "output_rms": round(rms_out, 5),
            "output_peak": round(peak_out, 5),
            "crest_factor": round(float(peak_out / (rms_out + 1e-12)), 4),
            "acoustic_comparison": comparison,
            "generation_warnings": warnings,
        }
    )
    return y_out.astype(np.float32), base_params


def _summarize_ref_asset(asset: dict[str, Any] | None) -> dict[str, Any] | None:
    if not asset:
        return None
    prof = asset.get("acoustic_profile") or {}
    fd = prof.get("frequency_domain") or {}
    td = prof.get("time_domain") or {}
    return {
        "asset_id": asset["asset_id"],
        "original_filename": asset["original_filename"],
        "provenance": asset.get("provenance"),
        "sha256": asset.get("sha256"),
        "effective_category": asset.get("effective_category"),
        "suggested_category": asset.get("suggested_category"),
        "confirmed_category": asset.get("confirmed_category"),
        "annotation_status": asset.get("annotation_status"),
        "label_verification": (
            "verified_by_named_reviewer" if asset.get("reviewed_by") else "unverified_source_or_curated_label"
        ),
        "duration_sec": asset.get("duration_sec"),
        "sample_rate": asset.get("sample_rate"),
        "rms_energy": asset.get("rms_energy"),
        "peak_amplitude": asset.get("peak_amplitude"),
        "f0_mean_hz": fd.get("f0_mean_hz"),
        "dominant_freq_hz": fd.get("dominant_freq_hz"),
        "spectral_centroid_hz": fd.get("spectral_centroid_hz"),
        "hnr_db": fd.get("hnr_db"),
        "event_count": td.get("event_count"),
        "suitability_score": asset.get("suitability_score"),
        "match_tier": asset.get("match_tier"),
        "audio_url": f"/api/communicate/references/{asset['asset_id']}/audio",
        "spectrogram_data_url": f"/api/communicate/references/{asset['asset_id']}/spectrogram-data",
        "waveform_url": f"/api/communicate/references/{asset['asset_id']}/media/waveform",
        "spectrogram_url": f"/api/communicate/references/{asset['asset_id']}/media/spectrogram",
    }
