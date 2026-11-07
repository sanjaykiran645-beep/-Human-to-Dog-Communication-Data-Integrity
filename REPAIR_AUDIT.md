# CanineSense AI — Complete Engineering Repair & Validation Audit

## 1. Root-Cause Report

1. **Post-Response Database Commit Race Condition (`Could not load media` on Analyze & Communicate)**
   - **Files:** `backend/app/db.py`, `backend/app/routers/recordings.py`, `backend/app/routers/communicate.py`, `backend/app/routers/auth.py`, `backend/app/routers/dogs.py`, `backend/app/routers/analytics.py`.
   - **Root Cause:** FastAPI generator dependencies (`get_db` with `yield db`) run post-yield cleanup (`db.commit()`) *after* the HTTP response has already been serialized and transmitted. Route handlers only called `db.flush()`, so immediate follow-up `GET /api/recordings/{id}/media/waveform` or `GET /api/communicate/{id}/audio` requests hit a separate SQLite connection before `db.commit()` finished, returning `404 Not Found` (`"Could not load media"`).
   - **Fix:** Added explicit `db.commit()` inside every write endpoint prior to returning the HTTP response, wrapped file + database writes in transactional recovery blocks that delete orphan files on failure, and added automatic plot regeneration if a historical recording's PNG plot is missing on disk.

2. **Communicate Foreign-Key Flush Ordering & Retry/Idempotency**
   - **Files:** `backend/app/routers/communicate.py`, `backend/app/schemas.py`.
   - **Root Cause:** `record_response` previously staged `Recording`, `Analysis` (FK -> `recordings.id`), and `DogResponse` (FK -> `generated_audio.id`, `recordings.id`, `analyses.id`) in a single un-ordered batch before calling `db.flush()`, and did not deduplicate retried uploads or generation requests.
   - **Fix:** Enforced sequential dependency flushing (`db.add(rec)` -> `db.flush()` -> `db.add(analysis)` -> `db.flush()` -> `db.add(resp)` -> `db.flush()` -> `db.commit()`), added SHA-256 duplicate response detection per `generated_id`, and added `idempotency_key` deduplication for `/api/communicate/generate`.

3. **Engine B Synthesis Determinism, Parameter Validation & WAV Verification**
   - **Files:** `backend/app/services/synthesis.py`, `backend/app/services/intent.py`.
   - **Root Cause:** `synthesis.py` used a mutable module-level `RNG = np.random.default_rng(7)` (violating deterministic output for identical settings), tiled/truncated waveforms abruptly when `duration_sec` was specified, and relied on post-hoc `librosa.effects.pitch_shift` (causing deprecation warnings and phase-vocoder artifacts).
   - **Fix:** Implemented `calculate_synthesis_parameters()` and deterministic seed derivation per parameter set across 7 supported profiles (`bark`, `growl`, `whine`, `howl`, `yip`, `grunt`, `soft_attention`) with harmonic glottal sources, subharmonics, cascade vocal-tract formant resonators, bandpass aspiration noise, FM/AM modulation, ADSR envelopes, boundary cosine tapers, and on-disk WAV verification (`validate_generated_wav`).

4. **STFT Spectrogram Pipeline & Interactive Visualization**
   - **Files:** `backend/app/services/spectrogram.py`, `backend/app/services/viz.py`, `frontend/src/components/SpectrogramViewer.tsx`.
   - **Root Cause:** `viz.py` previously computed only a static 64-bin mel PNG with `ref=np.max` (causing pure silence to render at `0 dB` instead of `-80 dBFS`), did not expose STFT parameters (`window`, `n_fft`, `hop_length`, `freq_resolution_hz`), and offered no interactive time/frequency inspection or zoom.
   - **Fix:** Built a validated STFT pipeline (`compute_spectrogram`, Hann window, `n_fft=1024`, `hop_length=256`, `Δf=21.53 Hz` at `22050 Hz`, calibrated `0 dBFS` reference with `-80 dBFS` silence floor) and an interactive HTML5 canvas `SpectrogramViewer` with Hz/kHz toggle, 1×/2×/4× zoom, time pan, hover crosshair inspector, colorbar legend, and side-by-side comparison between generated and response audio.

5. **Engine A Abstention Safeguards & Unified Audio Player**
   - **Files:** `backend/app/services/classifier.py`, `backend/app/services/explain.py`, `frontend/src/components/AudioPlayer.tsx`, `frontend/src/components/ResultView.tsx`.
   - **Root Cause:** `classify()` did not explicitly guard against empty/missing feature dicts, NaN/Inf feature values, or `event_count == 0`, and raw `<audio>` elements lacked unified Play/Pause/Resume/Stop/Replay state management or single-active-player coordination.
   - **Fix:** Added `_validate_features` in `classifier.py` to force abstention (`unknown`) on missing, non-finite, or event-free signals; marked unavailable measurements (`f0_mean` when unvoiced) as `"Unavailable"` in `explain.py`; and built `AudioPlayer.tsx` with coordinated single-instance playback and full transport controls.
