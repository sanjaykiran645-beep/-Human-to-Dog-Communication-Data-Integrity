"""
Reproducible builder for CanineSense AI Engine A's trainable, dog-ID-disjoint audio corpus.

Sources (all publicly accessible, no-auth-required, open/CC-licensed for ML training):
  1. FSD50K (Zenodo 10.5281/zenodo.4060432 metadata + HF philgzl/fsd50k Parquet shards)
     Licenses: Per-clip verified CC0-1.0, CC-BY-3.0, or CC-BY-NC-3.0 (Sampling+ excluded).
     dog_id: fsd50k_u_<uploader> (strict uploader-level grouping).
  2. ESC-50 (GitHub karolpiczak/ESC-50)
     License: CC-BY-NC-3.0.
     dog_id: esc50_src_<src_file> (strict Freesound source recording grouping,
     deduplicated against all FSD50K Freesound clip IDs to prevent cross-dataset leakage).
  3. cgeorgiaw/animal-sounds (HF dogs Parquet shards)
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

from app.config import TARGET_SR
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
    "pig", "boar", "horse", "cow", "sheep", "goat", "frog", "bird", "crow", "duck", "chicken",
    "wolf", "coyote", "fox", "hyena", "seal", "whale", "dolphin", "monkey", "ape", "gorilla",
    "reversed",
}

DOG_TERMS = {
    "dog", "dogs", "puppy", "puppies", "canine", "hound", "beagle", "husky", "terrier", "poodle",
    "chihuahua", "retriever", "labrador", "bulldog", "shepherd", "rottweiler", "dachshund", "pug",
    "spaniel", "mastiff", "collie", "pitbull", "boxer", "corgi", "doberman", "mutt", "doggy", "doggie",
    "bark", "barking", "woof", "chien", "hund", "perro", "koira",
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unknown"


def _http_get_with_retry(
    url: str,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
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
            timeout=60,
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
# Audio decoding, validation, and normalization
# ---------------------------------------------------------------------------

def _processed_path(cand: dict[str, Any]) -> Path:
    src_slug = _slug(cand["source"])
    clip_key = cand.get("fid") or cand.get("filename") or str(cand.get("row_idx"))
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


def decode_and_normalize(src_path: Path, dest_wav: Path) -> tuple[bool, str]:
    """
    Decode raw audio, validate duration/silence/finiteness, and write 22,050 Hz mono PCM_16 WAV.
    Returns (ok, reason).
    """
    if _is_valid_processed_wav(dest_wav):
        return True, "cached"

    y: np.ndarray | None = None
    sr: int | None = None

    # 1. Try soundfile directly
    try:
        y_raw, sr_raw = sf.read(str(src_path), dtype="float32", always_2d=False)
        y = np.asarray(y_raw, dtype=np.float32)
        sr = int(sr_raw)
    except Exception:
        y = None

    # 2. Fallback to ffmpeg
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

    # 3. Fallback to librosa
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

    # DC removal + resample to 22,050 Hz
    y = y - float(np.mean(y))
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
        sr = TARGET_SR

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
                title_toks = _tokens(title)
                all_toks = _tokens(title + " " + tags_str)

                if "reversed" in title_toks:
                    continue
                has_dog_context = bool(labs & {"Dog", "Bark", "Whimper_(dog)"}) or bool(all_toks & DOG_TERMS)
                has_non_dog_title = bool(title_toks & NON_DOG_TERMS) and not bool(title_toks & DOG_TERMS)
                if has_non_dog_title:
                    continue

                uploader = m.get("uploader") or f"unknown_{fid}"
                dog_id = f"fsd50k_u_{_slug(uploader)}"
                label: str | None = None

                if "Whimper_(dog)" in labs:
                    label = "whine"
                elif has_dog_context and not (labs & {"Bark", "Growling", "Howl"}) and bool(
                    title_toks & {"whine", "whining", "whines", "whimper", "whimpering", "cry", "crying"}
                ):
                    label = "whine"
                elif has_dog_context and not (labs & {"Bark", "Growling", "Howl", "Whimper_(dog)"}) and (
                    bool(title_toks & {"grunt", "grunts", "grunting", "groan", "groans", "groaning", "snort", "snorting", "sigh", "sighing", "huffing", "huff"})
                    or "doggrunt" in title.lower()
                ):
                    label = "grunt"
                elif "Yip" in labs and has_dog_context and "howl" not in title_toks:
                    label = "yip"
                elif has_dog_context and not (labs & {"Growling", "Howl"}) and bool(
                    title_toks & {"yip", "yips", "yipping", "yelp", "yelping", "yelps"}
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
    """Map philgzl/fsd50k (dev/eval) Parquet shards and cache exact row counts per shard."""
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
    """Download FSD50K clips directly from HuggingFace Hub Parquet shards with resume support."""
    fsd_dir = RAW_DIR / "fsd50k"
    fsd_dir.mkdir(parents=True, exist_ok=True)

    ready: list[tuple[dict[str, Any], Path]] = []
    to_fetch: list[dict[str, Any]] = []

    for c in cands:
        raw_dest = fsd_dir / f"{c['split']}_{c['fid']}.wav"
        proc_dest = _processed_path(c)
        if _is_valid_processed_wav(proc_dest):
            ready.append((c, proc_dest))
        elif raw_dest.exists() and raw_dest.stat().st_size > 500:
            ready.append((c, raw_dest))
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

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 2))) as pool:
        futs = [pool.submit(_download_shard_group, item) for item in by_shard.items()]
        for fut in as_completed(futs):
            ready.extend(fut.result())

    print(f"[FSD50K] Ready clips: {len(ready)}/{len(cands)} (0 rate-limit skips)")
    return ready


# ---------------------------------------------------------------------------
# Source 2: ESC-50 (GitHub karolpiczak/ESC-50)
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
# Source 3: cgeorgiaw/animal-sounds (HF dogs Parquet shards)
# ---------------------------------------------------------------------------

def download_animal_sounds_via_parquet(workers: int = 2) -> list[tuple[dict[str, Any], Path]]:
    """Load named-dog bark clips from cgeorgiaw/animal-sounds via cached raw files or direct Parquet streaming."""
    audio_dir = RAW_DIR / "animal_sounds" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # First check already cached raw files on disk
    existing_files = sorted(audio_dir.glob("animalsounds_dog_*.wav"))
    if len(existing_files) >= 120:
        ready_cached: list[tuple[dict[str, Any], Path]] = []
        per_dog: Counter[str] = Counter()
        for fpath in existing_files:
            # Filename pattern: animalsounds_dog_<name>_<row_idx>.wav
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

            # Check if any need bytes fetched from this row group
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

    # 1. Select & stream candidates across all 3 open-licensed sources
    gt_zip, meta_zip = ensure_fsd50k_metadata()
    fsd_cands, fsd_all_fids = select_fsd50k_candidates(gt_zip, meta_zip)
    print(f"[FSD50K] Selected {len(fsd_cands)} open-licensed canine candidates.")

    esc_cands = collect_esc50_candidates(fsd_all_fids)
    print(f"[ESC-50] Selected {len(esc_cands)} deduplicated candidates (dog + other).")

    downloaded: list[tuple[dict[str, Any], Path]] = []
    downloaded.extend(download_fsd50k_via_parquet(fsd_cands, workers=args.workers))
    downloaded.extend(download_esc50_clips(esc_cands, workers=args.workers))
    downloaded.extend(download_animal_sounds_via_parquet(workers=args.workers))

    # 2. Convert/normalize to 22,050 Hz mono PCM_16 WAV & filter corrupt/silent/<0.25s
    manifest_rows: list[dict[str, Any]] = []
    filter_reasons: Counter[str] = Counter()

    def _process_one(item: tuple[dict[str, Any], Path]) -> tuple[dict[str, Any] | None, str]:
        cand, raw_path = item
        dest_wav = _processed_path(cand)
        ok, reason = decode_and_normalize(raw_path, dest_wav)
        if not ok:
            return None, reason.split(" ")[0]
        return {
            "path": str(dest_wav.resolve()),
            "dog_id": cand["dog_id"],
            "label": cand["label"],
            "is_fixture": "False",
            "source": cand["source"],
            "license": cand["license"],
        }, "ok"

    print(f"\nNormalizing {len(downloaded)} clips to {TARGET_SR} Hz mono WAV (with resume support)...")
    with ThreadPoolExecutor(max_workers=max(1, args.workers * 2)) as pool:
        futs = [pool.submit(_process_one, item) for item in downloaded]
        for fut in as_completed(futs):
            row, reason = fut.result()
            if row is not None:
                manifest_rows.append(row)
            else:
                filter_reasons[reason] += 1

    manifest_rows.sort(key=lambda r: (r["label"], r["dog_id"], r["path"]))

    for r in manifest_rows:
        assert "reference_library" not in r["path"].lower(), f"Forbidden path: {r['path']}"
        assert r["label"] in CLASSES, f"Invalid label: {r['label']}"

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["path", "dog_id", "label", "is_fixture", "source", "license"]
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\nWrote {len(manifest_rows)} rows to {MANIFEST_PATH}")
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
