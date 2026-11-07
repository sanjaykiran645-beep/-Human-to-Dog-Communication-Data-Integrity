"""Waveform and STFT spectrogram image rendering. Generated from the validated processed signal only."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from .audio import load_processed
from .spectrogram import DEFAULT_HOP_LENGTH, DEFAULT_N_FFT, DEFAULT_WINDOW, MIN_DB_FLOOR, compute_spectrogram

_LOCK = threading.Lock()

_CMAP = LinearSegmentedColormap.from_list(
    "canine",
    ["#F7F3EC", "#E8D5B5", "#C45C26", "#6B2B12", "#1C1917"],
)


def write_plots(y: np.ndarray, sr: int, wave_path: Path, spec_path: Path) -> dict:
    """Render waveform.png and spectrogram.png atomically from signal y and return STFT summary metadata."""
    y_arr = np.asarray(y, dtype=np.float32)
    spec_data = compute_spectrogram(
        y_arr,
        sr=int(sr),
        n_fft=DEFAULT_N_FFT,
        hop_length=DEFAULT_HOP_LENGTH,
        window=DEFAULT_WINDOW,
    )
    with _LOCK:
        _waveform(y_arr, int(sr), wave_path)
        _spectrogram_plot(spec_data, spec_path)
    return spec_data


def ensure_plots(wav_path: Path, wave_path: Path, spec_path: Path) -> None:
    """Thread-safe plot check and atomic generation so concurrent waveform/spectrogram requests never race."""
    with _LOCK:
        wave_ok = wave_path.exists() and wave_path.stat().st_size > 128
        spec_ok = spec_path.exists() and spec_path.stat().st_size > 128
        if wave_ok and spec_ok:
            return
        y, sr = load_processed(wav_path)
        y_arr = np.asarray(y, dtype=np.float32)
        spec_data = compute_spectrogram(
            y_arr,
            sr=int(sr),
            n_fft=DEFAULT_N_FFT,
            hop_length=DEFAULT_HOP_LENGTH,
            window=DEFAULT_WINDOW,
        )
        if not wave_ok:
            _waveform(y_arr, int(sr), wave_path)
        if not spec_ok:
            _spectrogram_plot(spec_data, spec_path)


def _atomic_savefig(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.stem}.{uuid.uuid4().hex[:8]}.tmp.png")
    try:
        fig.savefig(tmp_path, format="png", facecolor=fig.get_facecolor())
        os.replace(tmp_path, path)
    finally:
        plt.close(fig)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _waveform(y: np.ndarray, sr: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.5, 1.8), dpi=120)
    fig.patch.set_facecolor("#F7F3EC")
    ax.set_facecolor("#F7F3EC")
    mono = y if y.ndim == 1 else np.mean(y, axis=-1)
    t = np.linspace(0.0, mono.size / sr, num=mono.size) if mono.size else np.array([0.0, 1.0])
    step = max(1, mono.size // 4000)
    if mono.size:
        ax.plot(t[::step], mono[::step], color="#C45C26", lw=0.85)
    ax.axhline(0.0, color="#E7E0D4", lw=0.6, ls="--")
    ax.set_xlim(0.0, float(t[-1]) if t.size else 1.0)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("Time (s)", color="#57534E", fontsize=8)
    ax.set_ylabel("Amplitude", color="#57534E", fontsize=8)
    ax.tick_params(colors="#78716C", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#E7E0D4")
    fig.tight_layout(pad=0.3)
    _atomic_savefig(fig, path)


def _spectrogram_plot(spec_data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    grid = spec_data["grid"]
    cfg = spec_data["stft_config"]
    metrics = spec_data["signal_metrics"]

    times = np.asarray(grid["times_sec"], dtype=np.float32)
    freqs = np.asarray(grid["freqs_hz"], dtype=np.float32)
    S_db = np.asarray(grid["db"], dtype=np.float32)

    max_f = min(8000.0, float(cfg["nyquist_hz"]))
    f_mask = freqs <= max_f
    if np.any(f_mask):
        freqs = freqs[f_mask]
        S_db = S_db[f_mask, :]

    fig, ax = plt.subplots(figsize=(9.5, 3.4), dpi=120)
    fig.patch.set_facecolor("#F7F3EC")
    ax.set_facecolor("#F7F3EC")

    t_min = float(times[0]) if times.size else 0.0
    t_max = max(t_min + 0.01, float(times[-1]) if times.size else 1.0)
    f_min = float(freqs[0]) if freqs.size else 0.0
    f_max = max(f_min + 100.0, float(freqs[-1]) if freqs.size else 8000.0)

    img = ax.imshow(
        S_db,
        origin="lower",
        aspect="auto",
        extent=[t_min, t_max, f_min, f_max],
        cmap=_CMAP,
        vmin=MIN_DB_FLOOR,
        vmax=0.0,
        interpolation="bilinear",
    )
    peak_note = f"Peak: {metrics['peak_freq_hz']:.0f} Hz" if metrics.get("peak_freq_hz") else "Silent signal"
    ax.set_title(
        f"STFT Spectrogram ({cfg['window'].capitalize()} window, N={cfg['n_fft']}, hop={cfg['hop_length']}, "
        f"Δf={cfg['freq_resolution_hz']} Hz) · {peak_note}",
        color="#57534E",
        fontsize=8,
        pad=5,
    )
    ax.set_xlabel("Time (s)", color="#57534E", fontsize=8)
    ax.set_ylabel("Frequency (Hz)", color="#57534E", fontsize=8)
    ax.tick_params(colors="#78716C", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#E7E0D4")
    cbar = fig.colorbar(img, ax=ax, format="%+2.0f dBFS", pad=0.02)
    cbar.set_label("Intensity (dBFS)", color="#57534E", fontsize=7)
    cbar.ax.tick_params(labelsize=7, colors="#78716C")
    fig.tight_layout(pad=0.4)
    _atomic_savefig(fig, path)
