"""
Reproducible builder for CanineSense AI Engine A's trainable, dog-ID-disjoint audio corpus.

Sources (all publicly accessible, no-auth-required, open/CC-licensed for ML training):
  1. FSD50K (Zenodo 10.5281/zenodo.4060432 metadata + HF philgzl/fsd50k Parquet shards)
     Licenses: Per-clip verified CC0-1.0, CC-BY-3.0, or CC-BY-NC-3.0 (Sampling+ excluded).
     dog_id: fsd50k_u_<uploader> (strict uploader-level grouping).
  2. agkphysics/AudioSet (Google AudioSet balanced train/eval Parquet shards on HF Hub)
     License: CC-BY-4.0.
     dog_id: audioset_yt_<video_id> (strict YouTube source video/dog grouping).
     Targeted expansion for minority classes whine ('Whimper (dog)') and yip ('Yip').
  3. ESC-50 (GitHub karolpiczak/ESC-50)
     License: CC-BY-NC-3.0.
     dog_id: esc50_src_<src_file> (strict Freesound source recording grouping,
     deduplicated against all FSD50K Freesound clip IDs to prevent cross-dataset leakage).
  4. cgeorgiaw/animal-sounds (HF dogs Parquet shards)
     License: CC-BY-4.0.
     dog_id: animalsounds_dog_<dog_name> (explicit individual named dogs).

NEVER polls datasets-server.huggingface.co/rows (streams directly from HF Hub Parquet shards
via pyarrow + HTTP Range requests with Retry-After / exponential backoff and resume support).
NEVER reads or includes any rows from data/reference_library/manifest.csv.
NEVER generates synthetic audio.

Outputs:
  - Raw cached downloads: data/ml_corpus/raw/
  - Normalized 22,050 Hz mono 16-bit PCM WAVs: data/ml_corpus/processed/
  - Manifest CSV: data/ml_corpus/trainable_manifest.csv
    Columns: path,dog_id,label,is_fixture,source,license
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import pyarrow.parquet as pq
import requests
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import DATA_DIR, TARGET_SR
from app.services.audio import find_ffmpeg
from app.services.classifier import CLASSES

CORPUS_ROOT = REPO_ROOT / "data" / "ml_corpus"
RAW_DIR = CORPUS_ROOT / "raw"
PROCESSED_DIR = CORPUS_ROOT / "processed"
MANIFEST_PATH = CORPUS_ROOT / "trainable_manifest.csv"

MIN_DURATION_SEC = 0.25
MAX_DURATION_SEC = 60.0
MIN_RMS = 5e-4
MIN_PEAK = 1e-3
MAX_SILENCE_RATIO = 0.92

MAX_CLIPS_PER_DOG_BY_CLASS = {
    "grunt": 20,
    "whine": 20,
    "yip": 20,
    "growl": 20,
    "other": 20,
    "howl": 6,
    "bark": 2,
}
AUDIOSET_TARGET_WHINE = 36
AUDIOSET_TARGET_YIP = 36

ESC50_OTHER_CATEGORIES = (
    "cat",
    "chirping_birds",
    "rain",
    "wind",
    "footsteps",
    "door_wood_knock",
    "clock_tick",
    "breathing",
    "coughing",
    "snoring",
    "vacuum_cleaner",
    "car_horn",
    "siren",
)
ESC50_OTHER_PER_CAT = 8
ANIMAL_SOUNDS_MAX_PER_DOG = 15

ALLOWED_FSD50K_LICENSES = {
    "http://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
    "http://creativecommons.org/licenses/by/3.0/": "CC-BY-3.0",
    "http://creativecommons.org/licenses/by-nc/3.0/": "CC-BY-NC-3.0",
}

NON_DOG_TERMS = {
    "cat", "kitten", "meow", "purr", "tiger", "lion", "bear", "panther", "leopard", "cheetah",
    "monster", "zombie", "dragon", "demon", "orc", "dinosaur", "alien", "human", "man", "woman",
    "baby", "child", "pig", "boar", "horse", "cow", "sheep", "goat", "frog", "bird", "crow",
    "duck", "chicken", "wolf", "coyote", "fox", "hyena", "seal", "whale", "dolphin", "monkey",
    "ape", "gorilla", "reversed", "toy",
}

DOG_TERMS = {
    "dog", "dogs", "puppy", "puppies", "canine", "hound", "beagle", "husky", "terrier", "poodle",
    "chihuahua", "retriever", "labrador", "bulldog", "shepherd", "rottweiler", "dachshund", "pug",
    "spaniel", "mastiff", "collie", "pitbull", "boxer", "corgi", "doberman", "mutt", "doggy", "doggie",
    "bark", "barking", "woof", "chien", "hund", "perro", "koira",
}

_YAMNET_ORT: Any = False


def _get_yamnet_localizer() -> Any:
    global _YAMNET_ORT
    if _YAMNET_ORT is not False:
        return _YAMNET_ORT
    onnx_path = DATA_DIR / "models" / "pretrained" / "yamnet.onnx"
    if not onnx_path.exists():
        _YAMNET_ORT = None
        return None
    try:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        _YAMNET_ORT = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
    except Exception:
        _YAMNET_ORT = None
    return _YAMNET_ORT


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unknown"


def _http_get_with_retry(
    url: str,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    retries: int = 5,
) -> requests.Response:
    sess = session or requests.Session()
    last_err = "unknown_error"
    for attempt in range(retries):
        try:
            resp = sess.get(url, headers=headers, timeout=timeout)
            if resp.status_code in {429, 500, 502, 503, 504}:
                retry_after = resp.headers.get("Retry-After")
                wait_s = float(retry_after) if (retry_after and retry_after.isdigit()) else (1.5 * (2 ** attempt))
                last_err = f"HTTP {resp.status_code} ({resp.reason})"
                time.sleep(min(wait_s, 30.0))
                continue
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(min(1.5 * (2 ** attempt), 20.0))
    raise RuntimeError(f"GET failed after {retries} attempts for {url}: {last_err}")


class HTTPRangeFile(io.RawIOBase):
    """Seekable file-like object over HTTP Range requests for zero-rate-limit Parquet streaming."""

    def __init__(self, url: str, session: requests.Session, tail_cache_bytes: int = 393216) -> None:
        self.url = url
        self.session = session
        r = _http_get_with_retry(url, session=self.session, headers={"Range": "bytes=0-0"}, timeout=30)
        self.final_url = r.url
        cr = r.headers.get("Content-Range", "")
        self.size = int(cr.split("/")[-1]) if "/" in cr else int(r.headers.get("Content-Length", 0))
        self.pos = 0
        self.tail_start = max(0, self.size - tail_cache_bytes)
        r_tail = _http_get_with_retry(
            self.final_url,
            session=self.session,
            headers={"Range": f"bytes={self.tail_start}-{self.size - 1}"},
            timeout=30,
        )
        self.tail_data = r_tail.content

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def read(self, size: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        if size < 0 or self.pos + size > self.size:
            size = self.size - self.pos
        if size == 0:
            return b""
        if self.pos >= self.tail_start:
            off = self.pos - self.tail_start
            data = self.tail_data[off : off + size]
            self.pos += len(data)
            return data
        end = min(self.size - 1, self.pos + size - 1)
        r = _http_get_with_retry(
            self.final_url,
            session=self.session,
            headers={"Range": f"bytes={self.pos}-{end}"},
            timeout=90,
        )
        data = r.content
        self.pos += len(data)
        return data

    def readinto(self, b: bytearray | memoryview) -> int:
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n


# ---------------------------------------------------------------------------
# Audio decoding, event localization, validation, and normalization
# ---------------------------------------------------------------------------

def _processed_path(cand: dict[str, Any]) -> Path:
    src_slug = _slug(cand["source"])
    clip_key = cand.get("fid") or cand.get("video_id") or cand.get("filename") or str(cand.get("row_idx"))
    clip_slug = _slug(Path(str(clip_key)).stem)
    return PROCESSED_DIR / cand["label"] / f"{src_slug}_{cand['dog_id']}_{clip_slug}.wav"


def _is_valid_processed_wav(dest_wav: Path) -> bool:
    if not dest_wav.exists() or dest_wav.stat().st_size <= 1000:
        return False
    try:
        info = sf.info(str(dest_wav))
        return info.samplerate == TARGET_SR and info.channels == 1 and info.duration >= MIN_DURATION_SEC
    except Exception:
        return False


def localize_vocalization_window(y: np.ndarray, sr: int, label: str) -> np.ndarray:
    """
    For multi-second weakly-labeled recordings (whine, yip, growl, howl from AudioSet/FSD50K),
    use pretrained YAMNet ONNX frame scores + RMS energy envelope to crop the recording to the
    primary active vocalization bout, stripping human speech, barks, and background noise.
    """
    dur = float(y.size / sr) if sr else 0.0
    if label not in {"whine", "yip", "growl", "howl"} or dur <= 1.25:
        return y

    sess = _get_yamnet_localizer()
    win_map = {"whine": 1.65, "yip": 0.62, "growl": 2.15, "howl": 2.65}
    target_win_sec = win_map.get(label, 1.80)
    target_samples = int(target_win_sec * sr)

    if sess is not None and dur >= 1.25:
        try:
            y16 = librosa.resample(y, orig_sr=sr, target_sr=16000).astype(np.float32)
            if y16.size >= 16000:
                scores, _, _ = sess.run(None, {"waveform": y16})
                if label == "whine":
                    # 75:Whimper(dog), 21:Whimper, 22:Crying, 355:Squeak, 69:Dog vs 70:Bark, 0:Speech
                    f_scores = (
                        3.2 * scores[:, 75]
                        + 2.6 * scores[:, 21]
                        + 1.4 * scores[:, 22]
                        + 0.9 * scores[:, 355]
                        + 0.6 * scores[:, 69]
                        - 0.5 * scores[:, 70]
                        - 0.9 * scores[:, 0]
                    )
                elif label == "yip":
                    # 71:Yip, 355:Squeak, 70:Bark, 73:Bow-wow, 69:Dog vs 74:Growling, 72:Howl, 0:Speech
                    f_scores = (
                        3.5 * scores[:, 71]
                        + 1.6 * scores[:, 355]
                        + 0.9 * scores[:, 70]
                        + 0.8 * scores[:, 73]
                        + 0.6 * scores[:, 69]
                        - 0.8 * scores[:, 74]
                        - 0.8 * scores[:, 72]
                        - 0.9 * scores[:, 0]
                    )
                elif label == "growl":
                    # 74:Growling, 34:Grunt, 35:Groan, 104:Roaring, 69:Dog vs 70:Bark, 71:Yip, 0:Speech
                    f_scores = (
                        3.8 * scores[:, 74]
                        + 1.2 * scores[:, 34]
                        + 1.0 * scores[:, 35]
                        + 0.8 * scores[:, 104]
                        + 0.6 * scores[:, 69]
                        - 0.8 * scores[:, 70]
                        - 0.8 * scores[:, 71]
                        - 0.9 * scores[:, 0]
                    )
                else:
                    # howl: 72:Howl, 117:Canidae, 69:Dog vs 70:Bark, 71:Yip, 0:Speech
                    f_scores = (
                        3.8 * scores[:, 72]
                        + 1.2 * scores[:, 117]
                        + 0.6 * scores[:, 69]
                        - 0.7 * scores[:, 70]
                        - 0.7 * scores[:, 71]
                        - 0.9 * scores[:, 0]
                    )
                best_t = int(np.argmax(f_scores))
                center_sec = best_t * 0.48 + 0.48
                half_span = max(0.85, target_win_sec * 0.65)
                search_s = max(0, int((center_sec - half_span) * sr))
                search_e = min(y.size, int((center_sec + half_span) * sr))
                region = y[search_s:search_e]
                if region.size > target_samples:
                    hop = max(1, int(0.03 * sr))
                    best_off = 0
                    best_rms = -1.0
                    for off in range(0, region.size - target_samples + 1, hop):
                        r_val = float(np.mean(region[off : off + target_samples] ** 2))
                        if r_val > best_rms:
                            best_rms = r_val
                            best_off = off
                    cropped = region[best_off : best_off + target_samples]
                    if float(np.sqrt(np.mean(cropped ** 2))) >= MIN_RMS:
                        return cropped
                elif region.size >= int(0.30 * sr):
                    if float(np.sqrt(np.mean(region ** 2))) >= MIN_RMS:
                        return region
        except Exception:
            pass

    if y.size > target_samples:
        hop = max(1, int(0.04 * sr))
        best_s = 0
        best_e_val = -1.0
        for s in range(0, y.size - target_samples + 1, hop):
            e_val = float(np.mean(y[s : s + target_samples] ** 2))
            if e_val > best_e_val:
                best_e_val = e_val
                best_s = s
        return y[best_s : best_s + target_samples]
    return y


def decode_and_normalize(src_path: Path, dest_wav: Path, label: str = "") -> tuple[bool, str]:
    """
    Decode raw audio, localize active vocalization window for minority classes,
    validate duration/silence/finiteness, and write 22,050 Hz mono PCM_16 WAV.
    """
    if _is_valid_processed_wav(dest_wav):
        return True, "cached"

    y: np.ndarray | None = None
    sr: int | None = None

    try:
        y_raw, sr_raw = sf.read(str(src_path), dtype="float32", always_2d=False)
        y = np.asarray(y_raw, dtype=np.float32)
        sr = int(sr_raw)
    except Exception:
        y = None

    if y is None:
        exe = find_ffmpeg()
        if exe:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                cmd = [
                    exe, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(src_path), "-ac", "1", "-ar", str(TARGET_SR),
                    "-sample_fmt", "s16", str(tmp_path),
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=30, check=False, stdin=subprocess.DEVNULL)
                if res.returncode == 0 and tmp_path.exists():
                    y_raw, sr_raw = sf.read(str(tmp_path), dtype="float32", always_2d=False)
                    y = np.asarray(y_raw, dtype=np.float32)
                    sr = int(sr_raw)
            finally:
                tmp_path.unlink(missing_ok=True)

    if y is None:
        try:
            y_raw, sr_raw = librosa.load(str(src_path), sr=TARGET_SR, mono=True)
            y = np.asarray(y_raw, dtype=np.float32)
            sr = int(sr_raw)
        except Exception as exc:
            return False, f"decode_failed: {exc}"

    if y is None or sr is None or y.size == 0:
        return False, "empty"

    if y.ndim > 1:
        y = np.mean(y, axis=-1)
    if not np.isfinite(y).all():
        return False, "non_finite"

    y = y - float(np.mean(y))
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
        sr = TARGET_SR

    if label in {"whine", "yip", "growl", "howl"}:
        y = localize_vocalization_window(y, sr, label)

    duration = float(y.size / sr)
    if duration < MIN_DURATION_SEC:
        return False, f"too_short ({duration:.3f}s)"
    if duration > MAX_DURATION_SEC:
        win = int(MAX_DURATION_SEC * sr)
        y = y[:win]
        duration = float(y.size / sr)

    rms = float(np.sqrt(np.mean(y ** 2)))
    peak = float(np.max(np.abs(y)))
    if rms < MIN_RMS or peak < MIN_PEAK:
        return False, f"silent (rms={rms:.6f}, peak={peak:.6f})"

    frame = max(1, int(0.02 * sr))
    hop = max(1, frame // 2)
    energies = [float(np.sqrt(np.mean(y[i : i + frame] ** 2))) for i in range(0, max(1, y.size - frame), hop)]
    energies_a = np.asarray(energies) if energies else np.array([rms])
    silence_thresh = max(1e-4, float(np.percentile(energies_a, 20)) * 0.5, rms * 0.08)
    silence_ratio = float(np.mean(energies_a < silence_thresh))
    if silence_ratio > MAX_SILENCE_RATIO:
        return False, f"mostly_silence ({silence_ratio:.2f})"

    if peak > 0.99:
        y = y * (0.99 / peak)

    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest_wav), y.astype(np.float32), TARGET_SR, subtype="PCM_16")
    return True, "ok"


# ---------------------------------------------------------------------------
# Source 1: FSD50K (Zenodo metadata + HF philgzl/fsd50k Parquet shards)
# ---------------------------------------------------------------------------

def ensure_fsd50k_metadata() -> tuple[Path, Path]:
    meta_dir = RAW_DIR / "fsd50k_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    gt_zip = meta_dir / "FSD50K.ground_truth.zip"
    meta_zip = meta_dir / "FSD50K.metadata.zip"
    for dest, url in [
        (gt_zip, "https://zenodo.org/api/records/4060432/files/FSD50K.ground_truth.zip/content"),
        (meta_zip, "https://zenodo.org/api/records/4060432/files/FSD50K.metadata.zip/content"),
    ]:
        if not dest.exists():
            print(f"[FSD50K] Downloading {dest.name} from Zenodo...")
            resp = _http_get_with_retry(url, timeout=120)
            dest.write_bytes(resp.content)
    return gt_zip, meta_zip


def select_fsd50k_candidates(gt_zip: Path, meta_zip: Path) -> tuple[list[dict[str, Any]], set[str]]:
    gt_zf = zipfile.ZipFile(gt_zip)
    meta_zf = zipfile.ZipFile(meta_zip)

    clips_meta: dict[str, dict[str, Any]] = {}
    for mname in ["FSD50K.metadata/dev_clips_info_FSD50K.json", "FSD50K.metadata/eval_clips_info_FSD50K.json"]:
        clips_meta.update(json.loads(meta_zf.read(mname).decode("utf-8")))

    split_index_map: dict[str, dict[str, int]] = {}
    for split_name, csv_name in [("dev", "FSD50K.ground_truth/dev.csv"), ("eval", "FSD50K.ground_truth/eval.csv")]:
        with gt_zf.open(csv_name) as fh:
            fnames = [row["fname"].strip() for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))]
        split_index_map[split_name] = {fid: idx for idx, fid in enumerate(sorted(fnames))}

    candidates: list[dict[str, Any]] = []
    dog_class_counts: Counter[tuple[str, str]] = Counter()

    for split_name, cname in [
        ("dev", "FSD50K.metadata/collection/collection_dev.csv"),
        ("eval", "FSD50K.metadata/collection/collection_eval.csv"),
    ]:
        with meta_zf.open(cname) as fh:
            for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8")):
                fid = row["fname"].strip()
                labs = {l.strip() for l in row["labels"].split(",")}
                m = clips_meta.get(fid, {})
                lic_url = m.get("license", "")
                if lic_url not in ALLOWED_FSD50K_LICENSES:
                    continue
                lic_short = ALLOWED_FSD50K_LICENSES[lic_url]
                title = m.get("title", "")
                tags_str = " ".join(m.get("tags", []))
                desc_str = m.get("description", "")
                title_toks = _tokens(title)
                tag_toks = _tokens(tags_str)
                desc_toks = _tokens(desc_str)
                all_toks = title_toks | tag_toks

                if "reversed" in all_toks:
                    continue
                has_dog_context = bool(labs & {"Dog", "Bark", "Whimper_(dog)", "Yip"}) or bool(all_toks & DOG_TERMS)
                has_non_dog_title = bool(title_toks & NON_DOG_TERMS) and not bool(title_toks & DOG_TERMS)
                if has_non_dog_title:
                    continue

                uploader = m.get("uploader") or f"unknown_{fid}"
                dog_id = f"fsd50k_u_{_slug(uploader)}"
                label: str | None = None

                # Expanded whine & yip mapping using human-verified FSD50K labels + title/tags/description
                if "Whimper_(dog)" in labs or ("Whimper" in labs and has_dog_context):
                    label = "whine"
                elif has_dog_context and not (labs & {"Growling", "Howl"}) and bool(
                    (title_toks | tag_toks | desc_toks)
                    & {"whine", "whining", "whines", "whimper", "whimpering", "whimpers", "cry", "crying", "plaintive"}
                ):
                    label = "whine"
                elif has_dog_context and not (labs & {"Bark", "Growling", "Howl", "Whimper_(dog)"}) and (
                    bool(title_toks & {"grunt", "grunts", "grunting", "groan", "groans", "groaning", "snort", "snorting", "sigh", "sighing", "huffing", "huff"})
                    or "doggrunt" in title.lower()
                ):
                    label = "grunt"
                elif "Yip" in labs and has_dog_context and "howl" not in title_toks:
                    label = "yip"
                elif has_dog_context and not (labs & {"Growling", "Howl", "Whimper_(dog)"}) and (
                    bool((title_toks | tag_toks | desc_toks) & {"yip", "yips", "yipping", "yelp", "yelping", "yelps", "yap", "yapping", "yaps"})
                    or bool((title_toks | tag_toks) & {"puppy", "puppies", "chihuahua"})
                ):
                    label = "yip"
                elif "Growling" in labs and has_dog_context and not (
                    bool(title_toks & {"bark", "barking", "barks"}) and "growl" not in title.lower()
                ):
                    label = "growl"
                elif "Howl" in labs and has_dog_context and "Howl_(wind)" not in labs:
                    label = "howl"
                elif "Bark" in labs and not (labs & {"Growling", "Howl", "Yip", "Whimper_(dog)"}) and not bool(
                    title_toks & {"growl", "growling", "howl", "howling", "whine", "whining", "whimper", "grunt", "yelp", "yip"}
                ):
                    label = "bark"
                elif has_dog_context and not (labs & {"Bark", "Growling", "Howl", "Yip", "Whimper_(dog)"}) and (
                    "Pant" in labs or bool(title_toks & {"pant", "panting", "pant1", "pant2", "pant3", "jadeo"})
                ):
                    label = "other"

                if label is None:
                    continue

                raw_dest = RAW_DIR / "fsd50k" / f"{split_name}_{fid}.wav"
                already_cached = raw_dest.exists() and raw_dest.stat().st_size > 500
                cap = MAX_CLIPS_PER_DOG_BY_CLASS.get(label, 20)
                if not already_cached and dog_class_counts[(dog_id, label)] >= cap:
                    continue

                row_idx = split_index_map[split_name].get(fid)
                if row_idx is None:
                    continue

                dog_class_counts[(dog_id, label)] += 1
                candidates.append({
                    "split": split_name,
                    "fid": fid,
                    "row_idx": row_idx,
                    "dog_id": dog_id,
                    "label": label,
                    "source": "FSD50K",
                    "license": lic_short,
                    "title": title,
                })

    return candidates, set(clips_meta.keys())


def _get_fsd50k_shard_index(workers: int = 2) -> dict[str, dict[str, Any]]:
    cache_file = RAW_DIR / "fsd50k_meta" / "parquet_shard_index.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    print("[FSD50K] Indexing philgzl/fsd50k Parquet shard footers from HuggingFace Hub...")
    sess = requests.Session()
    r = _http_get_with_retry("https://huggingface.co/api/datasets/philgzl/fsd50k/parquet/default", session=sess, timeout=30)
    parquet_map = r.json()

    index_data: dict[str, dict[str, Any]] = {}
    for split_name in ("dev", "eval"):
        urls = parquet_map.get(split_name, [])

        def _fetch_rows(idx_url: tuple[int, str]) -> tuple[int, int]:
            s_idx, u = idx_url
            local_sess = requests.Session()
            rf = HTTPRangeFile(u, local_sess)
            pf = pq.ParquetFile(io.BufferedReader(rf, buffer_size=65536))
            return s_idx, int(pf.metadata.num_rows)

        counts = [0] * len(urls)
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
            for s_idx, nrows in pool.map(_fetch_rows, enumerate(urls)):
                counts[s_idx] = nrows

        cum_starts = []
        acc = 0
        for c in counts:
            cum_starts.append(acc)
            acc += c
        index_data[split_name] = {"urls": urls, "counts": counts, "cum_starts": cum_starts}

    cache_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")
    return index_data


def download_fsd50k_via_parquet(cands: list[dict[str, Any]], workers: int = 2) -> list[tuple[dict[str, Any], Path]]:
    fsd_dir = RAW_DIR / "fsd50k"
    fsd_dir.mkdir(parents=True, exist_ok=True)

    ready: list[tuple[dict[str, Any], Path]] = []
    to_fetch: list[dict[str, Any]] = []

    for c in cands:
        raw_dest = fsd_dir / f"{c['split']}_{c['fid']}.wav"
        proc_dest = _processed_path(c)
        if raw_dest.exists() and raw_dest.stat().st_size > 500:
            ready.append((c, raw_dest))
        elif _is_valid_processed_wav(proc_dest):
            ready.append((c, proc_dest))
        else:
            to_fetch.append(c)

    if not to_fetch:
        print(f"[FSD50K] All {len(ready)} clips already cached/processed.")
        return ready

    shard_index = _get_fsd50k_shard_index(workers=workers)
    by_shard: dict[tuple[str, int], list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for c in to_fetch:
        sp = c["split"]
        row_idx = int(c["row_idx"])
        cum_starts = shard_index[sp]["cum_starts"]
        shard_idx = bisect.bisect_right(cum_starts, row_idx) - 1
        local_rg = row_idx - cum_starts[shard_idx]
        by_shard[(sp, shard_idx)].append((local_rg, c))

    print(f"[FSD50K] Streaming {len(to_fetch)} uncached clips across {len(by_shard)} Parquet shards (cached={len(ready)})...")

    def _download_shard_group(item: tuple[tuple[str, int], list[tuple[int, dict[str, Any]]]]) -> list[tuple[dict[str, Any], Path]]:
        (sp, shard_idx), group_items = item
        shard_url = shard_index[sp]["urls"][shard_idx]
        local_sess = requests.Session()
        rf = HTTPRangeFile(shard_url, local_sess)
        pf = pq.ParquetFile(io.BufferedReader(rf, buffer_size=524288))
        out: list[tuple[dict[str, Any], Path]] = []
        for local_rg, cand in sorted(group_items, key=lambda x: x[0]):
            raw_dest = fsd_dir / f"{cand['split']}_{cand['fid']}.wav"
            tbl = pf.read_row_group(local_rg, columns=["name", "audio"])
            audio_val = tbl["audio"][0].as_py()
            raw_bytes = audio_val["bytes"] if isinstance(audio_val, dict) else audio_val
            raw_dest.write_bytes(raw_bytes)
            out.append((cand, raw_dest))
        return out

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
        futs = [pool.submit(_download_shard_group, item) for item in by_shard.items()]
        for fut in as_completed(futs):
            ready.extend(fut.result())

    print(f"[FSD50K] Ready clips: {len(ready)}/{len(cands)} (0 rate-limit skips)")
    return ready


# ---------------------------------------------------------------------------
# Source 2: agkphysics/AudioSet (Google AudioSet balanced Parquet shards on HF Hub)
# ---------------------------------------------------------------------------

def ensure_audioset_canine_index(workers: int = 4) -> list[dict[str, Any]]:
    meta_dir = RAW_DIR / "audioset_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    index_path = meta_dir / "canine_index.json"
    if index_path.exists():
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    print("[AudioSet] Scanning agkphysics/AudioSet balanced Parquet shards for Whimper (dog) and Yip...")
    sess = requests.Session()
    splits = _http_get_with_retry("https://huggingface.co/api/datasets/agkphysics/AudioSet/parquet/balanced", session=sess, timeout=30).json()
    tasks = [(sp, s_idx, url) for sp in ("test", "train") for s_idx, url in enumerate(splits.get(sp, []))]

    def _scan(item: tuple[str, int, str]) -> list[dict[str, Any]]:
        sp, s_idx, url = item
        local_sess = requests.Session()
        rf = HTTPRangeFile(url, local_sess)
        pf = pq.ParquetFile(io.BufferedReader(rf, buffer_size=131072))
        hits = []
        for rg_idx in range(pf.metadata.num_row_groups):
            tbl = pf.read_row_group(rg_idx, columns=["video_id", "human_labels"])
            for local_i, (vid, hl) in enumerate(zip(tbl["video_id"].to_pylist(), tbl["human_labels"].to_pylist())):
                hset = set(hl or [])
                if "Whimper (dog)" in hset or "Yip" in hset or ("Dog" in hset and "Whimper" in hset):
                    hits.append({
                        "split": sp,
                        "shard_idx": s_idx,
                        "shard_url": url,
                        "rg_idx": rg_idx,
                        "local_idx": local_i,
                        "video_id": vid,
                        "human_labels": sorted(hset),
                    })
        return hits

    all_hits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for res in pool.map(_scan, tasks):
            all_hits.extend(res)
    index_path.write_text(json.dumps(all_hits, indent=2), encoding="utf-8")
    return all_hits


def download_audioset_whine_yip(workers: int = 4) -> list[tuple[dict[str, Any], Path]]:
    """
    Select and stream pure Whimper (dog) ('whine') and Yip ('yip') clips from
    agkphysics/AudioSet balanced Parquet shards (CC-BY-4.0), packing multi-hit
    row groups first and caching raw FLAC/WAV clips in data/ml_corpus/raw/audioset/.
    """
    hits = ensure_audioset_canine_index(workers=workers)
    as_dir = RAW_DIR / "audioset"
    as_dir.mkdir(parents=True, exist_ok=True)

    by_rg: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for h in hits:
        hset = set(h["human_labels"])
        label: str | None = None
        if ("Whimper (dog)" in hset or ("Dog" in hset and "Whimper" in hset)) and not (
            hset & {"Bark", "Growling", "Howl"}
        ):
            label = "whine"
        elif "Yip" in hset and not (hset & {"Growling", "Howl", "Whimper (dog)"}):
            label = "yip"
        if label is None:
            continue

        vid = h["video_id"]
        cand = {
            "split": h["split"],
            "shard_idx": h["shard_idx"],
            "shard_url": h["shard_url"],
            "rg_idx": h["rg_idx"],
            "local_idx": h["local_idx"],
            "video_id": vid,
            "dog_id": f"audioset_yt_{_slug(vid)}",
            "label": label,
            "source": "AudioSet",
            "license": "CC-BY-4.0",
        }
        by_rg[(h["split"], h["shard_idx"], h["rg_idx"])].append(cand)

    # Prioritize row groups that already have cached files or pack multiple whine/yip hits
    def _rg_priority(kv: tuple[tuple[str, int, int], list[dict[str, Any]]]) -> tuple[int, int, tuple[str, int, int]]:
        rg_key, items = kv
        cached_cnt = sum(1 for c in items if (as_dir / f"{c['split']}_{c['video_id']}.flac").exists())
        return (-cached_cnt, -len(items), rg_key)

    sorted_rgs = sorted(by_rg.items(), key=_rg_priority)

    selected_rgs: list[tuple[tuple[str, int, int], list[dict[str, Any]]]] = []
    w_vids: set[str] = set()
    y_vids: set[str] = set()

    for rg_key, items in sorted_rgs:
        keep_items = []
        for it in items:
            if it["label"] == "whine" and len(w_vids) < AUDIOSET_TARGET_WHINE and it["video_id"] not in w_vids:
                w_vids.add(it["video_id"])
                keep_items.append(it)
            elif it["label"] == "yip" and len(y_vids) < AUDIOSET_TARGET_YIP and it["video_id"] not in y_vids:
                y_vids.add(it["video_id"])
                keep_items.append(it)
        if keep_items:
            selected_rgs.append((rg_key, keep_items))
        if len(w_vids) >= AUDIOSET_TARGET_WHINE and len(y_vids) >= AUDIOSET_TARGET_YIP:
            break

    ready: list[tuple[dict[str, Any], Path]] = []
    rgs_to_fetch: list[tuple[tuple[str, int, int], list[dict[str, Any]]]] = []

    for rg_key, items in selected_rgs:
        missing = []
        for c in items:
            raw_dest = as_dir / f"{c['split']}_{c['video_id']}.flac"
            if raw_dest.exists() and raw_dest.stat().st_size > 500:
                ready.append((c, raw_dest))
            else:
                missing.append(c)
        if missing:
            rgs_to_fetch.append((rg_key, missing))

    if not rgs_to_fetch:
        print(f"[AudioSet] All {len(ready)} selected whine/yip clips already cached.")
        return ready

    print(
        f"[AudioSet] Streaming {sum(len(m) for _, m in rgs_to_fetch)} new whine/yip clips "
        f"across {len(rgs_to_fetch)} row groups (cached={len(ready)})..."
    )

    def _fetch_rg(item: tuple[tuple[str, int, int], list[dict[str, Any]]]) -> list[tuple[dict[str, Any], Path]]:
        (sp, s_idx, rg_idx), cands_in_rg = item
        shard_url = cands_in_rg[0]["shard_url"]
        local_sess = requests.Session()
        rf = HTTPRangeFile(shard_url, local_sess)
        # Use 32 MB buffer so the row group streams in 4 fast chunks instead of 34 small round-trips
        pf = pq.ParquetFile(io.BufferedReader(rf, buffer_size=33554432))
        tbl = pf.read_row_group(rg_idx, columns=["audio"])
        audio_col = tbl["audio"]
        out: list[tuple[dict[str, Any], Path]] = []
        for cand in cands_in_rg:
            raw_dest = as_dir / f"{cand['split']}_{cand['video_id']}.flac"
            audio_val = audio_col[int(cand["local_idx"])].as_py()
            raw_bytes = audio_val["bytes"] if isinstance(audio_val, dict) else audio_val
            raw_dest.write_bytes(raw_bytes)
            out.append((cand, raw_dest))
        return out

    with ThreadPoolExecutor(max_workers=max(1, min(workers * 3, 8))) as pool:
        futs = [pool.submit(_fetch_rg, item) for item in rgs_to_fetch]
        for fut in as_completed(futs):
            ready.extend(fut.result())

    print(f"[AudioSet] Ready whine/yip clips: {len(ready)} (0 rate-limit skips)")
    return ready


# ---------------------------------------------------------------------------
# Source 3: ESC-50 (GitHub karolpiczak/ESC-50)
# ---------------------------------------------------------------------------

def collect_esc50_candidates(fsd50k_all_fids: set[str]) -> list[dict[str, Any]]:
    meta_dir = RAW_DIR / "esc50"
    meta_dir.mkdir(parents=True, exist_ok=True)
    csv_path = meta_dir / "esc50.csv"
    if not csv_path.exists():
        print("[ESC-50] Downloading esc50.csv from GitHub...")
        resp = _http_get_with_retry("https://raw.githubusercontent.com/karolpiczak/ESC-50/master/meta/esc50.csv", timeout=30)
        csv_path.write_bytes(resp.content)

    candidates: list[dict[str, Any]] = []
    other_cat_counts: Counter[str] = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cat = row["category"].strip().lower()
            src_file = row["src_file"].strip()
            fname = row["filename"].strip()
            if src_file in fsd50k_all_fids:
                continue

            label: str | None = None
            if cat == "dog":
                label = "bark"
            elif cat in ESC50_OTHER_CATEGORIES and other_cat_counts[cat] < ESC50_OTHER_PER_CAT:
                label = "other"
                other_cat_counts[cat] += 1

            if label is None:
                continue

            candidates.append({
                "filename": fname,
                "src_file": src_file,
                "dog_id": f"esc50_src_{src_file}",
                "label": label,
                "source": "ESC-50",
                "license": "CC-BY-NC-3.0",
            })
    return candidates


def download_esc50_clips(cands: list[dict[str, Any]], workers: int = 2) -> list[tuple[dict[str, Any], Path]]:
    audio_dir = RAW_DIR / "esc50" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    ready: list[tuple[dict[str, Any], Path]] = []

    def _dl_one(cand: dict[str, Any]) -> tuple[dict[str, Any], Path]:
        proc_dest = _processed_path(cand)
        if _is_valid_processed_wav(proc_dest):
            return cand, proc_dest
        raw_dest = audio_dir / cand["filename"]
        if raw_dest.exists() and raw_dest.stat().st_size > 500:
            return cand, raw_dest
        url = f"https://raw.githubusercontent.com/karolpiczak/ESC-50/master/audio/{cand['filename']}"
        r = _http_get_with_retry(url, timeout=30)
        raw_dest.write_bytes(r.content)
        return cand, raw_dest

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for fut in as_completed([pool.submit(_dl_one, c) for c in cands]):
            ready.append(fut.result())

    print(f"[ESC-50] Ready clips: {len(ready)}/{len(cands)}")
    return ready


# ---------------------------------------------------------------------------
# Source 4: cgeorgiaw/animal-sounds (HF dogs Parquet shards)
# ---------------------------------------------------------------------------

def download_animal_sounds_via_parquet(workers: int = 2) -> list[tuple[dict[str, Any], Path]]:
    audio_dir = RAW_DIR / "animal_sounds" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    existing_files = sorted(audio_dir.glob("animalsounds_dog_*.wav"))
    if len(existing_files) >= 120:
        ready_cached: list[tuple[dict[str, Any], Path]] = []
        per_dog: Counter[str] = Counter()
        for fpath in existing_files:
            m = re.match(r"^(animalsounds_dog_[a-z0-9]+)_(\d+)\.wav$", fpath.name)
            if not m:
                continue
            dog_id, row_idx_str = m.group(1), m.group(2)
            if per_dog[dog_id] >= ANIMAL_SOUNDS_MAX_PER_DOG:
                continue
            per_dog[dog_id] += 1
            cand = {
                "row_idx": int(row_idx_str),
                "dog_id": dog_id,
                "label": "bark",
                "source": "cgeorgiaw/animal-sounds",
                "license": "CC-BY-4.0",
            }
            ready_cached.append((cand, fpath))
        if ready_cached:
            print(f"[animal-sounds] Loaded {len(ready_cached)} cached named-dog clips from disk (0 rate-limit skips).")
            return ready_cached

    print("[animal-sounds] Streaming dogs config from HuggingFace Hub Parquet shards...")
    sess = requests.Session()
    urls = _http_get_with_retry(
        "https://huggingface.co/api/datasets/cgeorgiaw/animal-sounds/parquet/dogs/train",
        session=sess,
        timeout=30,
    ).json()

    ready: list[tuple[dict[str, Any], Path]] = []
    per_dog_counts: Counter[str] = Counter()
    global_idx = 0

    for shard_url in urls:
        rf = HTTPRangeFile(shard_url, sess)
        pf = pq.ParquetFile(io.BufferedReader(rf, buffer_size=1048576))
        for rg_idx in range(pf.metadata.num_row_groups):
            meta_tbl = pf.read_row_group(rg_idx, columns=["name"])
            names = meta_tbl["name"].to_pylist()
            needed_local_indices: list[tuple[int, int, str]] = []
            for local_i, raw_name in enumerate(names):
                row_idx = global_idx + local_i
                name = (raw_name or "").strip()
                if not name:
                    continue
                dog_id = f"animalsounds_dog_{_slug(name)}"
                if per_dog_counts[dog_id] >= ANIMAL_SOUNDS_MAX_PER_DOG:
                    continue
                per_dog_counts[dog_id] += 1
                needed_local_indices.append((local_i, row_idx, dog_id))

            global_idx += len(names)
            if not needed_local_indices:
                continue

            uncached_locals = [
                (li, r_idx, d_id)
                for li, r_idx, d_id in needed_local_indices
                if not (audio_dir / f"{d_id}_{r_idx}.wav").exists()
            ]
            bytes_col = None
            if uncached_locals:
                bytes_tbl = pf.read_row_group(rg_idx, columns=["bytes"])
                bytes_col = bytes_tbl["bytes"].to_pylist()

            for li, r_idx, d_id in needed_local_indices:
                raw_dest = audio_dir / f"{d_id}_{r_idx}.wav"
                if not raw_dest.exists() and bytes_col is not None:
                    raw_dest.write_bytes(bytes_col[li])
                cand = {
                    "row_idx": r_idx,
                    "dog_id": d_id,
                    "label": "bark",
                    "source": "cgeorgiaw/animal-sounds",
                    "license": "CC-BY-4.0",
                }
                ready.append((cand, raw_dest))

    print(f"[animal-sounds] Ready clips: {len(ready)} (0 rate-limit skips)")
    return ready


# ---------------------------------------------------------------------------
# Main pipeline + audit
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build trainable dog-disjoint audio corpus and manifest.")
    parser.add_argument("--workers", type=int, default=2, help="Polite parallel workers (default: 2).")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Clear cached processed growl/howl files so YAMNet active-event localization is applied cleanly (whine/yip already localized)
    for sub in ("growl", "howl"):
        sub_dir = PROCESSED_DIR / sub
        if sub_dir.exists():
            for old_wav in sub_dir.glob("*.wav"):
                old_wav.unlink(missing_ok=True)

    # 1. Select & stream candidates across all 4 open-licensed sources
    gt_zip, meta_zip = ensure_fsd50k_metadata()
    fsd_cands, fsd_all_fids = select_fsd50k_candidates(gt_zip, meta_zip)
    print(f"[FSD50K] Selected {len(fsd_cands)} open-licensed canine candidates.")

    esc_cands = collect_esc50_candidates(fsd_all_fids)
    print(f"[ESC-50] Selected {len(esc_cands)} deduplicated candidates (dog + other).")

    downloaded: list[tuple[dict[str, Any], Path]] = []
    downloaded.extend(download_fsd50k_via_parquet(fsd_cands, workers=args.workers))
    downloaded.extend(download_audioset_whine_yip(workers=args.workers))
    downloaded.extend(download_esc50_clips(esc_cands, workers=args.workers))
    downloaded.extend(download_animal_sounds_via_parquet(workers=args.workers))

    # 2. Convert/normalize to 22,050 Hz mono PCM_16 WAV & filter corrupt/silent/<0.25s
    raw_manifest_rows: list[dict[str, Any]] = []
    filter_reasons: Counter[str] = Counter()

    def _process_one(item: tuple[dict[str, Any], Path]) -> tuple[dict[str, Any] | None, str]:
        cand, raw_path = item
        dest_wav = _processed_path(cand)
        ok, reason = decode_and_normalize(raw_path, dest_wav, label=cand["label"])
        if not ok:
            return None, reason.split(" ")[0]
        audio_sha256 = hashlib.sha256(dest_wav.read_bytes()).hexdigest()
        return {
            "path": str(dest_wav.resolve()),
            "dog_id": cand["dog_id"],
            "label": cand["label"],
            "is_fixture": "False",
            "source": cand["source"],
            "license": cand["license"],
            "_sha256": audio_sha256,
        }, "ok"

    print(f"\nNormalizing {len(downloaded)} clips to {TARGET_SR} Hz mono WAV (with YAMNet localization & resume)...")
    with ThreadPoolExecutor(max_workers=max(1, args.workers * 2)) as pool:
        futs = [pool.submit(_process_one, item) for item in downloaded]
        for fut in as_completed(futs):
            row, reason = fut.result()
            if row is not None:
                raw_manifest_rows.append(row)
            else:
                filter_reasons[reason] += 1

    raw_manifest_rows.sort(key=lambda r: (r["label"], r["dog_id"], r["path"]))

    # Deduplicate by audio SHA-256 hash
    seen_hashes: set[str] = set()
    manifest_rows: list[dict[str, Any]] = []
    dup_cnt = 0
    for r in raw_manifest_rows:
        h = r.pop("_sha256")
        if h in seen_hashes:
            dup_cnt += 1
            continue
        seen_hashes.add(h)
        assert "reference_library" not in r["path"].lower(), f"Forbidden path: {r['path']}"
        assert r["label"] in CLASSES, f"Invalid label: {r['label']}"
        manifest_rows.append(r)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["path", "dog_id", "label", "is_fixture", "source", "license"]
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\nWrote {len(manifest_rows)} deduplicated rows to {MANIFEST_PATH} (duplicates_removed={dup_cnt})")
    if filter_reasons:
        print(f"Filtered out clips: {dict(filter_reasons)}")

    # 3. Audit manifest + verify dog-disjoint group_split & leakage_report
    from app.ml.evaluate import group_split, leakage_report, load_manifest

    loaded = load_manifest(MANIFEST_PATH)
    train_idx, test_idx = group_split(loaded)
    issues = leakage_report(loaded, train_idx, test_idx)
    print(f"Leakage check (group_split train={len(train_idx)}, test={len(test_idx)}): {'PASS (0 issues)' if not issues else issues}")

    by_class_clips: Counter[str] = Counter()
    by_class_dogs: dict[str, set[str]] = defaultdict(set)
    by_source: Counter[tuple[str, str]] = Counter()
    for r in loaded:
        by_class_clips[r["label"]] += 1
        by_class_dogs[r["label"]].add(r["dog_id"])
        by_source[(r["source"], r["license"])] += 1

    print("\n=== SOURCES & LICENSES ===")
    for (src, lic), cnt in sorted(by_source.items()):
        print(f"  {src:25s} | {lic:15s} | {cnt:4d} clips")

    print("\n=== PER-CLASS AUDIT ===")
    print(f"{'class':10s} | {'clips':>6s} | {'distinct_dogs':>13s} | status")
    print("-" * 50)
    for cls in CLASSES:
        c = by_class_clips[cls]
        d = len(by_class_dogs[cls])
        status = "OK (>=15 dogs)" if d >= 15 else f"SHORTFALL (-{15 - d} dogs)"
        print(f"{cls:10s} | {c:6d} | {d:13d} | {status}")
    all_dogs = {r["dog_id"] for r in loaded}
    print("-" * 50)
    print(f"{'TOTAL':10s} | {len(loaded):6d} | {len(all_dogs):13d} | unique dog_ids")


if __name__ == "__main__":
    main()
