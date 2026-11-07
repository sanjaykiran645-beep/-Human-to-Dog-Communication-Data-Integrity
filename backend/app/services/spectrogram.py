"""
Validated Short-Time Fourier Transform (STFT) spectrogram pipeline.

Pipeline stages:
1. Audio input (raw bytes, Path, or numpy array)
2. Decode & format verification
3. Validate sample rate (8000–96000 Hz)
4. Validate channel count (1–8 channels) & finite sample values (reject NaN/Inf)
5. Convert to mono float32 analysis representation
6. Frame audio & apply Hann window function
7. Short-Time Fourier Transform (STFT)
8. Calculate power spectrum |X(m, k)|^2
9. Convert to calibrated decibel scale (dBFS, floor -80 dB)
10. Generate spectrogram data structure & render visualization
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import get_window, stft

DEFAULT_N_FFT = 1024
DEFAULT_HOP_LENGTH = 256
DEFAULT_WINDOW = "hann"
MIN_DB_FLOOR = -80.0
SILENCE_PEAK_THRESH = 1e-4
SILENCE_RMS_THRESH = 2e-5
NEAR_SILENCE_RMS_THRESH = 8e-4


class SpectrogramError(ValueError):
    """Raised when audio input is invalid, corrupt, or cannot produce a valid spectrogram."""

    def __init__(self, message: str, code: str = "invalid_spectrogram_input") -> None:
        super().__init__(message)
        self.code = code


def compute_spectrogram_from_file(path: Path, max_time_frames: int = 240, max_freq_bins: int = 160) -> dict[str, Any]:
    """Decode an audio file from disk, validate it, and compute STFT spectrogram data."""
    if not path.exists() or not path.is_file():
        raise SpectrogramError("Audio file not found.", "not_found")
    if path.stat().st_size < 44:
        raise SpectrogramError("Audio file is too small or corrupt.", "corrupt_audio")
    try:
        y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as exc:
        raise SpectrogramError("Could not decode audio file for spectrogram analysis.", "decode_failed") from exc
    return compute_spectrogram(
        y,
        sr=int(sr),
        max_time_frames=max_time_frames,
        max_freq_bins=max_freq_bins,
    )


def compute_spectrogram(
    y: np.ndarray,
    sr: int,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
    window: str = DEFAULT_WINDOW,
    max_time_frames: int = 240,
    max_freq_bins: int = 160,
) -> dict[str, Any]:
    """
    Validate signal and compute STFT magnitude/power spectrogram in dBFS.

    Parameters
    ----------
    y : np.ndarray
        1D (mono) or 2D (frames, channels) audio array.
    sr : int
        Sample rate in Hz.
    n_fft : int
        STFT frame/FFT size in samples (default 1024).
    hop_length : int
        STFT hop size in samples (default 256).
    window : str
        Window function name (default 'hann').
    """
    if not isinstance(sr, (int, float)) or not np.isfinite(sr) or int(sr) < 1000 or int(sr) > 192000:
        raise SpectrogramError(f"Invalid sample rate: {sr}", "invalid_sample_rate")
    sr = int(sr)

    if not isinstance(y, np.ndarray):
        try:
            y = np.asarray(y, dtype=np.float32)
        except Exception as exc:
            raise SpectrogramError("Signal cannot be converted to float array.", "invalid_samples") from exc

    if y.size == 0:
        raise SpectrogramError("Audio signal contains zero samples.", "empty_signal")

    if not bool(np.isfinite(y).all()):
        raise SpectrogramError("Audio signal contains non-finite sample values (NaN or Inf).", "non_finite_samples")

    # Validate channel layout and convert to mono float32 representation
    if y.ndim == 1:
        original_channels = 1
        mono = y.astype(np.float32, copy=False)
    elif y.ndim == 2:
        # Handle both (samples, channels) and (channels, samples)
        if y.shape[1] <= 8 and y.shape[0] >= y.shape[1]:
            original_channels = int(y.shape[1])
            mono = np.mean(y, axis=1, dtype=np.float32)
        elif y.shape[0] <= 8:
            original_channels = int(y.shape[0])
            mono = np.mean(y, axis=0, dtype=np.float32)
        else:
            raise SpectrogramError(f"Unsupported channel count: {y.shape}", "invalid_channels")
    else:
        raise SpectrogramError(f"Unsupported array dimensions: {y.ndim}D", "invalid_dimensions")

    if original_channels < 1 or original_channels > 8:
        raise SpectrogramError(f"Invalid channel count: {original_channels}", "invalid_channels")

    n_samples = int(mono.size)
    if n_samples < 16:
        raise SpectrogramError(f"Audio signal is too short for spectral analysis ({n_samples} samples).", "too_short")

    duration_sec = float(n_samples / sr)
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(mono**2)))
    clipping_ratio = float(np.mean(np.abs(mono) >= 0.99))
    is_clipped = bool(clipping_ratio > 0.01 or peak > 1.0)
    is_silent = bool(peak < SILENCE_PEAK_THRESH or rms < SILENCE_RMS_THRESH)
    is_near_silent = bool((not is_silent) and rms < NEAR_SILENCE_RMS_THRESH)

    # Adapt frame size for very short clips while documenting effective STFT settings
    eff_n_fft = int(n_fft)
    if n_samples < eff_n_fft:
        # Choose largest power of 2 <= n_samples (at least 64), zero-padding if needed
        p2 = 1 << max(6, int(np.floor(np.log2(max(16, n_samples)))))
        eff_n_fft = min(int(n_fft), max(64, p2))
    eff_hop = min(int(hop_length), max(8, eff_n_fft // 4))
    noverlap = eff_n_fft - eff_hop

    win = get_window(window, eff_n_fft, fftbins=True)
    win_norm = float(np.sum(win)) + 1e-12

    # Compute Short-Time Fourier Transform
    freqs_hz, times_sec, Zxx = stft(
        mono,
        fs=sr,
        window=win,
        nperseg=eff_n_fft,
        noverlap=noverlap,
        nfft=eff_n_fft,
        boundary="zeros",
        padded=True,
    )

    # Normalized magnitude and power spectrum (0 dBFS = full-scale sine wave amplitude 1.0)
    mag = (np.abs(Zxx) * 2.0) / win_norm
    power = mag**2

    if is_silent:
        S_db = np.full_like(power, MIN_DB_FLOOR, dtype=np.float32)
        peak_freq_hz: float | None = None
        secondary_freq_hz: float | None = None
        frame_peak_freqs_hz: list[float] = []
        spectral_flatness = 1.0
    else:
        # Convert power to decibels relative to full scale (1.0), clamped to [MIN_DB_FLOOR, 0.0]
        S_db = 10.0 * np.log10(np.maximum(power, 10.0 ** (MIN_DB_FLOOR / 10.0))).astype(np.float32)
        S_db = np.clip(S_db, MIN_DB_FLOOR, 6.0)

        # Measure dominant frequency peaks from active frames (excluding DC bin 0)
        valid_bins = mag[1:, :] if mag.shape[0] > 1 else mag
        valid_freqs = freqs_hz[1:] if freqs_hz.size > 1 else freqs_hz
        frame_energy = np.sum(valid_bins**2, axis=0)
        energy_thresh = max(float(np.max(frame_energy)) * 0.05, 1e-12)
        active_mask = frame_energy >= energy_thresh
        active_mag = valid_bins[:, active_mask] if np.any(active_mask) else valid_bins

        mean_spectrum = np.mean(active_mag, axis=1)
        peak_idx = int(np.argmax(mean_spectrum))
        peak_freq_hz = round(float(valid_freqs[peak_idx]), 2)

        # Find secondary distinct spectral peak (at least 3 bins away from primary peak)
        suppressed = mean_spectrum.copy()
        lo = max(0, peak_idx - 3)
        hi = min(suppressed.size, peak_idx + 4)
        suppressed[lo:hi] = 0.0
        sec_idx = int(np.argmax(suppressed))
        if suppressed[sec_idx] >= 0.15 * mean_spectrum[peak_idx]:
            secondary_freq_hz = round(float(valid_freqs[sec_idx]), 2)
        else:
            secondary_freq_hz = None

        # Per-frame dominant frequency trajectory on active frames
        active_indices = np.where(active_mask)[0]
        frame_peak_freqs_hz = [
            round(float(valid_freqs[int(np.argmax(valid_bins[:, idx]))]), 2)
            for idx in active_indices
        ]

        # Spectral flatness (geometric mean / arithmetic mean of power spectrum)
        p_mean = np.mean(active_mag**2, axis=1) + 1e-15
        g_mean = float(np.exp(np.mean(np.log(p_mean))))
        a_mean = float(np.mean(p_mean))
        spectral_flatness = round(float(g_mean / (a_mean + 1e-15)), 4)

    freq_res_hz = float(sr / eff_n_fft)
    time_res_sec = float(eff_hop / sr)
    rms_db = float(20.0 * np.log10(max(rms, 10.0 ** (MIN_DB_FLOOR / 20.0))))
    peak_db = float(20.0 * np.log10(max(peak, 10.0 ** (MIN_DB_FLOOR / 20.0))))
    dyn_range_db = float(np.max(S_db) - np.percentile(S_db, 10)) if not is_silent else 0.0

    # Downsample grid for fast JSON interactive canvas rendering while preserving peak energy
    t_step = max(1, int(np.ceil(times_sec.size / max_time_frames)))
    f_step = max(1, int(np.ceil(freqs_hz.size / max_freq_bins)))
    ds_times = [round(float(t), 4) for t in times_sec[::t_step]]
    ds_freqs = [round(float(f), 1) for f in freqs_hz[::f_step]]
    ds_db = np.round(S_db[::f_step, ::t_step], 1).tolist()

    return {
        "valid": True,
        "sample_rate": sr,
        "original_channels": original_channels,
        "analysis_channels": 1,
        "sample_count": n_samples,
        "duration_sec": round(duration_sec, 4),
        "stft_config": {
            "window": window,
            "n_fft": eff_n_fft,
            "hop_length": eff_hop,
            "overlap_samples": noverlap,
            "freq_resolution_hz": round(freq_res_hz, 2),
            "time_resolution_sec": round(time_res_sec, 5),
            "nyquist_hz": round(sr / 2.0, 1),
            "db_floor": MIN_DB_FLOOR,
            "db_reference": "0 dBFS (full-scale sine)",
        },
        "signal_metrics": {
            "is_silent": is_silent,
            "is_near_silent": is_near_silent,
            "is_clipped": is_clipped,
            "clipping_ratio": round(clipping_ratio, 6),
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "rms_db": round(rms_db, 2),
            "peak_db": round(peak_db, 2),
            "dynamic_range_db": round(dyn_range_db, 2),
            "peak_freq_hz": peak_freq_hz,
            "secondary_freq_hz": secondary_freq_hz,
            "frame_peak_freqs_hz": frame_peak_freqs_hz[:64],
            "spectral_flatness": spectral_flatness,
        },
        "grid": {
            "times_sec": ds_times,
            "freqs_hz": ds_freqs,
            "db": ds_db,
            "min_db": MIN_DB_FLOOR,
            "max_db": 0.0,
        },
    }
