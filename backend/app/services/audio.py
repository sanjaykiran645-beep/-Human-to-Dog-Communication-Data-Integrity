"""Audio ingestion, validation, and preprocessing. Originals are preserved."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from ..config import ALLOWED_EXTENSIONS, MAX_DURATION_SEC, MAX_UPLOAD_BYTES, MIN_DURATION_SEC, TARGET_SR

_FFMPEG_CACHE: str | None | bool = False  # False = not probed


class AudioError(ValueError):
    def __init__(self, message: str, code: str = "invalid_audio") -> None:
        super().__init__(message)
        self.code = code


def find_ffmpeg() -> str | None:
    """Locate an ffmpeg executable. Env FFMPEG_PATH wins, then PATH, then common dirs."""
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE is not False:
        return _FFMPEG_CACHE  # type: ignore[return-value]
    env = os.getenv("FFMPEG_PATH", "").strip()
    candidates = []
    if env:
        candidates.append(env)
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)
    candidates.extend(
        [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
        ]
    )
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for found in winget_pkgs.glob("**/ffmpeg.exe"):
                candidates.append(str(found))
    for path in candidates:
        if path and Path(path).is_file():
            _FFMPEG_CACHE = path
            return path
    _FFMPEG_CACHE = None
    return None


def decoder_status() -> dict[str, Any]:
    exe = find_ffmpeg()
    codecs: list[str] = []
    version = None
    if exe:
        try:
            ver = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=25, stdin=subprocess.DEVNULL)
            version = (ver.stdout or "").splitlines()[0] if ver.returncode == 0 else None
            enc = subprocess.run([exe, "-hide_banner", "-decoders"], capture_output=True, text=True, timeout=25, stdin=subprocess.DEVNULL)
            text = enc.stdout or ""
            for name in ("opus", "vorbis", "aac", "mp3", "flac", "pcm", "alac"):
                if name in text.lower():
                    codecs.append(name)
        except (OSError, subprocess.TimeoutExpired):
            exe = None
    wav_ok = True
    try:
        import soundfile as _sf  # noqa: F401
    except Exception:
        wav_ok = False
    return {
        "ffmpeg_path": exe,
        "ffmpeg_available": bool(exe),
        "ffmpeg_version": version,
        "ffmpeg_decoders": codecs,
        "soundfile_wav": wav_ok,
        "supported_without_ffmpeg": ["wav", "flac"],
        "supported_with_ffmpeg": ["wav", "mp3", "m4a", "ogg", "webm", "weba", "flac"],
        "install_hint": (
            None
            if exe
            else "Install FFmpeg and ensure it is on PATH. Windows: winget install Gyan.FFmpeg. Debian/Ubuntu: sudo apt-get install ffmpeg."
        ),
    }


def sniff_format(header: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".mpeg", ".mpga"}:
        ext = ".mp3"
    if ext == ".weba":
        ext = ".webm"
    # Magic first — do not trust the extension alone, and allow missing extensions.
    if header.startswith(b"PK\x03\x04"):
        raise AudioError(
            "Uploaded file is a ZIP archive, not a single audio file. Extract the archive and upload a WAV, MP3, M4A, OGG, WEBM, or FLAC file.",
            "unsupported_format",
        )
    if header.startswith(b"RIFF") or header.startswith(b"RIFX"):
        return "wav"
    if header.startswith(b"OggS"):
        return "ogg"
    if header.startswith(b"fLaC"):
        return "flac"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "webm"
    if header[:3] == b"ID3" or header[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa", b"\xff\xf1"}:
        return "mp3"
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return "m4a"
    if ext in ALLOWED_EXTENSIONS or ext == ".webm":
        return ext.lstrip(".")
    if not ext:
        raise AudioError(
            "Could not recognize this audio. Use WAV, MP3, M4A, OGG, WEBM, or FLAC.",
            "unrecognized",
        )
    raise AudioError(
        f"Unsupported format '{ext}'. Use WAV, MP3, M4A, OGG, WEBM, or FLAC.",
        "unsupported_format",
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_and_decode(data: bytes, dest_original: Path, dest_wav: Path, filename: str) -> dict[str, Any]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise AudioError("File exceeds 15 MB limit.", "too_large")
    if len(data) < 64:
        raise AudioError("File is too small to be valid audio.", "too_small")
    fmt = sniff_format(data[:64], filename)
    dest_original.parent.mkdir(parents=True, exist_ok=True)
    dest_original.write_bytes(data)

    y, sr = _decode_any(dest_original, dest_wav, fmt)

    if y.size == 0:
        raise AudioError("The recording contains no samples.", "empty")

    duration = float(y.size / sr)
    if duration < MIN_DURATION_SEC:
        raise AudioError(
            f"Recording is too short ({duration:.2f}s). Need at least {MIN_DURATION_SEC:.2f}s of audio.",
            "too_short",
        )
    if duration > MAX_DURATION_SEC:
        raise AudioError(
            f"Recording is too long ({duration:.1f}s). Maximum is {int(MAX_DURATION_SEC)}s.",
            "too_long",
        )

    quality = assess_quality(y, sr)
    y_proc, proc_meta = preprocess(y, sr)
    _write_wav(dest_wav, y_proc, TARGET_SR)

    return {
        "y": y_proc,
        "sr": TARGET_SR,
        "original_sr": int(sr),
        "channels": 1,
        "duration": float(y_proc.size / TARGET_SR),
        "format": fmt,
        "quality": quality,
        "preprocess": proc_meta,
        "decoder": "soundfile" if fmt in {"wav", "flac"} and find_ffmpeg() else "ffmpeg_or_soundfile",
    }


def _decode_any(src: Path, dest_wav: Path, fmt: str) -> tuple[np.ndarray, int]:
    """Try soundfile (WAV/FLAC), then ffmpeg (WEBM/MP3/M4A/OGG), then librosa."""
    if fmt in {"wav", "flac"}:
        try:
            y, sr = _read_soundfile(src)
            if y.ndim > 1:
                y = np.mean(y, axis=1)
            return y.astype(np.float32), int(sr)
        except Exception:
            pass
    try:
        return _ffmpeg_decode(src, dest_wav)
    except AudioError:
        raise
    except Exception:
        pass
    try:
        import librosa

        y, sr = librosa.load(str(src), sr=None, mono=True)
        return np.asarray(y, dtype=np.float32), int(sr)
    except Exception as exc:
        raise AudioError("Could not decode this audio file. It may be corrupted.", "decode_failed") from exc


def _read_soundfile(path: Path) -> tuple[np.ndarray, int]:
    y, sr = sf.read(str(path), always_2d=False, dtype="float32")
    return np.asarray(y, dtype=np.float32), int(sr)


def _ffmpeg_decode(src: Path, dest_wav: Path) -> tuple[np.ndarray, int]:
    exe = find_ffmpeg()
    if not exe:
        raise AudioError(
            "Audio decoder (FFmpeg) is not available on the server. "
            "WAV and FLAC still work. For microphone WEBM/Opus, MP3, M4A, or OGG, install FFmpeg "
            "(Windows: winget install Gyan.FFmpeg; Linux: sudo apt-get install ffmpeg) and restart the API.",
            "decoder_missing",
        )
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        exe,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        str(TARGET_SR),
        "-sample_fmt",
        "s16",
        str(tmp_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=40, check=False, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise AudioError(
            "Audio decoder (FFmpeg) is not available on the server. Install FFmpeg and restart.",
            "decoder_missing",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        tmp_path.unlink(missing_ok=True)
        raise AudioError("Audio decoding timed out.", "decode_timeout") from exc
    if result.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        err = (result.stderr or b"").decode("utf-8", errors="replace")[:180]
        raise AudioError(
            "Could not decode this audio file. It may be corrupted or an unsupported codec."
            + (f" ({err})" if err else ""),
            "decode_failed",
        )
    try:
        y, sr = _read_soundfile(tmp_path)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        return y.astype(np.float32), int(sr)
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_wav(path: Path, y: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    out = y
    if peak > 1.0:
        out = y / peak * 0.99
    sf.write(str(path), out.astype(np.float32), sr, subtype="PCM_16")


def preprocess(y: np.ndarray, sr: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Mono, resample, light DC removal. Original file is not modified."""
    import librosa

    if y.ndim > 1:
        y = np.mean(y, axis=-1)
    y = np.asarray(y, dtype=np.float32)
    y = y - float(np.mean(y))
    orig_sr = sr
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
        sr = TARGET_SR
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    gain = 1.0
    if peak > 1.0:
        gain = 0.99 / peak
        y = y * gain
    return y.astype(np.float32), {"target_sr": TARGET_SR, "original_sr": orig_sr, "peak": peak, "gain": gain}


def assess_quality(y: np.ndarray, sr: int) -> dict[str, Any]:
    if y.size == 0:
        return {"status": "reject", "reasons": ["empty"], "snr_db": None, "silence_ratio": 1.0, "clipping_ratio": 0.0}

    rms = float(np.sqrt(np.mean(y**2)))
    peak = float(np.max(np.abs(y)))
    clipping_ratio = float(np.mean(np.abs(y) > 0.99))
    frame = max(1, int(0.02 * sr))
    hop = max(1, frame // 2)
    energies = []
    for i in range(0, max(1, y.size - frame), hop):
        energies.append(float(np.sqrt(np.mean(y[i : i + frame] ** 2))))
    energies_a = np.asarray(energies) if energies else np.array([rms])
    silence_thresh = max(1e-4, float(np.percentile(energies_a, 20)) * 0.5, rms * 0.08)
    silence_ratio = float(np.mean(energies_a < silence_thresh))
    noise_floor = float(np.percentile(energies_a, 10) + 1e-9)
    snr_db = float(20 * np.log10((rms + 1e-9) / noise_floor))

    reasons: list[str] = []
    status = "ok"
    if rms < 5e-4 or peak < 1e-3:
        reasons.append("Recording is effectively silent.")
        status = "reject"
    if silence_ratio > 0.92:
        reasons.append("More than 92% of the recording is silence.")
        status = "reject"
    if clipping_ratio > 0.08:
        reasons.append("Severe clipping detected; acoustic features will be distorted.")
        status = "poor"
    elif clipping_ratio > 0.02:
        reasons.append("Mild clipping detected.")
        status = "fair" if status == "ok" else status
    if snr_db < 6 and status != "reject":
        reasons.append("Low estimated signal-to-noise ratio.")
        status = "poor"
    elif snr_db < 12 and status == "ok":
        reasons.append("Moderate background noise.")
        status = "fair"

    return {
        "status": status,
        "reasons": reasons,
        "rms": rms,
        "peak": peak,
        "snr_db": snr_db,
        "silence_ratio": silence_ratio,
        "clipping_ratio": clipping_ratio,
        "crest_factor": float(peak / (rms + 1e-12)),
    }


def load_processed(path: Path) -> tuple[np.ndarray, int]:
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    return np.asarray(y, dtype=np.float32), int(sr)


def ffmpeg_encode(src_wav: Path, dest: Path, fmt: str) -> None:
    """Test helper: encode WAV to another container via ffmpeg."""
    exe = find_ffmpeg()
    if not exe:
        raise AudioError("ffmpeg missing", "decoder_missing")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src_wav), str(dest)]
    result = subprocess.run(cmd, capture_output=True, timeout=30, check=False, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not dest.exists():
        raise AudioError("ffmpeg encode failed", "encode_failed")
