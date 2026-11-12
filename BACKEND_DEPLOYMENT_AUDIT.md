# CANINESENSE AI — BACKEND DEPLOYMENT & PRODUCTION AUDIT REPORT (PHASE 2)

**Audit Date:** November 11, 2026  
**Auditor:** Antigravity Autonomous Systems Engineering & Security Verification Agent  
**Environment:** Production Cloud Deployment  
**Status:** **OPERATIONAL & LIVE** (Verification Score: **14/15 PASS**, 1 Remediated Locally, Storage Persistence Qualified)

---

## 1. Executive Summary & Service Coordinates

CanineSense AI's real FastAPI backend has been successfully containerized, deployed, and verified live on Render cloud infrastructure. The deployment connects directly with the existing GitHub Pages production frontend (`https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/`), enabling genuine full-stack functionality without mock data or simulated bypasses.

### Core Service Coordinates

| Parameter | Value / Detail |
|---|---|
| **Render Web Service Name** | `caninesense-backend` |
| **Render Service ID** | `srv-dbq9o9m7bikc73dctmq0` |
| **Live Production Backend URL** | `https://caninesense-backend.onrender.com` |
| **Live Health Check Endpoint** | `https://caninesense-backend.onrender.com/api/health` |
| **Render Region** | Oregon, USA (`us-west`) |
| **Active Live Deploy ID** | `dep-dbq9pqgu01pc73a811pg` (Built from Dockerfile) |
| **Deployed Git Commit** | `4968d86` |
| **Locally Prepared Remediated Commit** | `6608f24` (*"fix(reference_library): resolve absolute paths dynamically for container compatibility and configure production backend URL"*) |
| **Production Frontend (GitHub Pages)**| `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/` |
| **Source Code Repository** | `https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity.git` |

---

## 2. Phase 1 — Backend Readiness Verification

Prior to cloud deployment, the complete backend codebase underwent strict local inspection and verification:

1. **Unit & Integration Test Suite:**
   - Ran `pytest` across all backend test modules (`test_audio_and_model.py`, `test_auth.py`, `test_communicate.py`, `test_engine_b_integrity.py`, `test_formats_and_decoder.py`, `test_security_hardening.py`, `test_security_idor.py`, `test_synthesis_and_spectrogram.py`).
   - **Result:** **99 of 99 tests PASSED (100% passing rate)**.
2. **Audio Engine Integrity:**
   - Engine A (Acoustic Heuristic v1.0.0 with Librosa STFT, harmonic profiling, F0 estimation, and emotional valence mapping): fully intact.
   - Engine B (Bimodal Reference Library & Synthesis Engine): 184 processed audio clips, 63 raw audio clips, and synthesis modules verified intact.
3. **Decoders & System Binaries:**
   - System FFmpeg binary integration verified alongside SoundFile and Python wave decoders.
4. **Dynamic Port Support:**
   - Confirmed `Dockerfile` dynamically binds Uvicorn to `$PORT` (`--port ${PORT:-8000}`).

---

## 3. Phase 2 — Render Deployment Configuration

The backend was provisioned via the official Render CLI using interactive secure authentication without exposing passwords or hardcoded API keys.

### Container & Build Environment
- **Base Image:** `python:3.11-slim`
- **System Packages:** `ffmpeg`, `libsndfile1`, `curl`, `ca-certificates`
- **Application Directory:** `/app`
- **Entrypoint:** Dynamic port-binding Uvicorn ASGI server with standard worker configuration

### Cloud Environment Variables (Configured on Render)
All production environment variables were securely applied to the Web Service:
- `CANINESENSE_ENV=production`
- `CANINESENSE_DATA_DIR=/app/data`
- `CANINESENSE_SECRET_KEY=[48-byte cryptographically secure URL-safe entropy]`
- `CANINESENSE_ACCESS_TOKEN_MINUTES=1440` (24-hour token lifetime)
- `CANINESENSE_CORS_ORIGINS=https://sanjaykiran645-beep.github.io,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000`
- `CANINESENSE_TRUST_PROXY=1`

### Database Architecture & Storage Constraints Analysis

> [!WARNING]
> **Ephemeral Container Filesystem on Render Free Plan**  
> On Render's `free` web service tier, the container root filesystem is **ephemeral**. When the service enters inactivity spin-down (after 15 minutes of idle time) or is redeployed:
> 1. The SQLite database at `/app/data/caninesense.sqlite3` is wiped.
> 2. Uploaded user audio recordings in `/app/data/storage/recordings/` are erased.
> 3. User accounts created during that container lifecycle are reset.

#### Recommended Smallest Safe Corrections for Production Persistence:
1. **Option A (Recommended for Render): Starter Plan with Dedicated Persistent Disk**
   - Upgrade Render service `caninesense-backend` from Free to **Starter** ($7/month).
   - Attach a 1GB Persistent Disk ($0.25/month) mounted at `/var/caninesense_data` (or `/app/data_persist`).
   - Update `CANINESENSE_DATA_DIR=/var/caninesense_data` in Render environment variables.
   - *Crucial note:* **Do not mount the persistent disk directly over `/app/data`**, because doing so would overlay and mask the pre-baked reference library assets in `/app/data/reference_library/`. Keeping static reference assets in `/app/data/reference_library` and pointing dynamic database/uploads to `/var/caninesense_data` preserves both.
2. **Option B (Zero-Cost Production Separation): Managed External PostgreSQL + Object Storage**
   - Configure a free-tier external PostgreSQL database (e.g., Supabase, Neon, or Render PostgreSQL Free) and set `CANINESENSE_DATABASE_URL=postgresql://...`.
   - Offload user audio files to an S3-compatible bucket (e.g., Cloudflare R2 free tier).

---

## 4. Phase 3 — Frontend Connection Verification

### Frontend Inspection (GitHub Pages)
The live GitHub Pages site (`https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/#/login`) was inspected by an automated browser agent:
- **Visual Presentation:** Dual-card split-screen desktop layout, branding, waveform graphic, Engine A/B overviews, and authentication forms render with zero layout defects.
- **Authentication Forms:** "Sign in" and "Create account" tabs, email and password fields, and submit buttons are present and responsive.
- **Backend URL Resolution:**
  - In the currently deployed bundle on GitHub Pages, API requests default to relative paths (`/api/...`), which return HTTP 404 against static GitHub Pages hosting.
  - Users can immediately override the backend URL via the built-in UI: navigate to `#/app/settings`, input `https://caninesense-backend.onrender.com` under **"FastAPI Backend Origin URL"**, and click **"Save Backend URL"**.
  - In local commit `6608f24`, `frontend/src/api.ts` was updated with automatic runtime origin detection: when running on `github.io`, it automatically defaults to `https://caninesense-backend.onrender.com`. In addition, `frontend/.env.production` was created with `VITE_API_URL=https://caninesense-backend.onrender.com`.

---

## 5. Phase 4 — Real Live Cloud Functionality Test Suite

The 15 mandatory verification tests were executed against the live Render endpoint (`https://caninesense-backend.onrender.com`) using synthetic test audio and dedicated auditor test accounts.

### Complete Verification Results Matrix

| # | Test Case | Target Endpoint / Action | Live Result | Status | Technical Evidence & Observability |
|---|---|---|---|:---:|---|
| **1** | **Health Endpoint** | `GET /api/health` | HTTP 200 OK | **PASS** | `status: "ok"`, `version: "0.1.0"`, `decoder.ffmpeg_available: true`, decoders active. |
| **2** | **User Registration** | `POST /api/auth/register` | HTTP 200 OK | **PASS** | Created account `audit_a_1794416252@caninesense-audit.org`, stored bcrypt salt/hash, returned JWT token. |
| **3** | **User Login** | `POST /api/auth/login` | HTTP 200 OK | **PASS** | Authenticated with valid credentials; issued JWT bearer access token. |
| **4** | **Invalid Login Rejection** | `POST /api/auth/login` | HTTP 401 Unauthorized | **PASS** | Rejected invalid credentials with `"Incorrect email or password"`. |
| **5** | **Logout & Session Handling** | `POST /api/auth/logout` | HTTP 200 OK | **PASS** | JWT denylisted in token revocation table; subsequent call to `GET /api/auth/me` returned HTTP 401 Unauthorized. |
| **6** | **Authenticated Dashboard** | `GET /api/analytics/summary` | HTTP 200 OK | **PASS** | Retrieved live analytics row counts for authenticated user (`recordings: 0`, `dogs: 0`). |
| **7** | **Dog Profile Management** | `POST /api/dogs` & `GET /api/dogs/{id}` | HTTP 201 / 200 | **PASS** | Created dog "Barkley" (Golden Retriever, 31.0kg, ID: `17b2bbfd-4395-40bb-9711-c3c1222f5809`), retrieved accurately. |
| **8** | **Audio Upload** | `POST /api/recordings/analyze` | HTTP 200 OK | **PASS** | Uploaded genuine WAV sample `00bb5134-2bf0-4c0f-89c0-af7819291482-ev0.wav` (9,250 bytes, duration: 0.21s, rec_id: `87d93edf-...`). |
| **9** | **Engine A ML Inference** | Librosa STFT & Harmonic Analysis | Verified | **PASS** | Acoustic feature extraction executed: `vocalization: "bark"`, `confidence: 0.883`, `model: "acoustic-heuristic-v1.0.0"`. |
| **10** | **Engine B Reference Playback** | `GET /api/communicate/references/{id}/audio` | HTTP 404 (Commit `4968d86`) | **FAIL\*** | Catalog list returned HTTP 200 (128 assets), but audio streaming failed due to Windows host paths (`C:\Users\Admin\...`) in legacy `manifest.json`. **Fixed in local commit `6608f24` (99/99 tests pass locally); pending owner push.** |
| **11** | **Recording Archive & Media** | `GET /api/recordings/{id}/media/*` | HTTP 200 OK | **PASS** | Retrieved generated STFT spectrogram PNG (39,805 bytes) and processed WAV audio stream (9,250 bytes). |
| **12** | **User Data Isolation (IDOR)** | Cross-user object inspection | HTTP 404 Not Found | **PASS** | User B attempted to access User A's dog profile, recording record, and media file; all returned HTTP 404. |
| **13** | **Data Export** | `GET /api/account/export` | HTTP 200 OK | **PASS** | Downloaded comprehensive JSON research export containing dogs, recordings, and full acoustic analyses. |
| **14** | **Authorized Data Deletion** | `DELETE /api/account` | HTTP 200 OK | **PASS** | GDPR/Privacy compliant complete erasure of user record, dog profile, audio files, and spectrograms. Post-deletion login rejected with 401. |
| **15** | **Frontend Connectivity & CORS** | `OPTIONS /api/recordings/analyze` | HTTP 200 OK | **PASS** | Production Cloudflare TLS verified. CORS preflight returned `Access-Control-Allow-Origin: https://sanjaykiran645-beep.github.io` and allowed methods `GET, POST, PATCH, DELETE, OPTIONS`. |

---

## 6. Security & Compliance Findings

1. **Authentication Hardening:**
   - Password hashing uses bcrypt with cryptographically secure per-user salt.
   - JWT tokens use HMAC-SHA256 with a 48-byte cryptographically random secret.
   - Token revocation denylist table active and verified.
2. **Strict Origin Isolation:**
   - Wildcard CORS (`*`) is disabled in production.
   - Allowed origins are restricted strictly to `https://sanjaykiran645-beep.github.io` and local development loopbacks.
3. **Insecure Direct Object Reference (IDOR) Hardening:**
   - Verified that user database queries enforce ownership checks (`filter(models.Dog.owner_user_id == user.id)`).
   - Non-owner requests return HTTP 404 rather than 403, preventing object ID enumeration.
4. **Data Privacy & GDPR:**
   - Self-service research data export (`GET /api/account/export`) verified functional.
   - Cascading account deletion (`DELETE /api/account`) deletes user records, dog associations, and file artifacts on disk.
5. **Secret Hygiene:**
   - Zero production API keys, passwords, or tokens are committed into version control or exposed in frontend source files.

---

## 7. Failed Tests & Remediations

### Test 10: Engine B Reference Audio Playback (HTTP 404)
- **Observed Behavior on Deployed Container (Commit `4968d86`):**
  Listing reference clips (`GET /api/communicate/references`) succeeded, but attempting to stream reference audio (`GET /api/communicate/references/{id}/audio`) returned HTTP 404 Not Found.
- **Root Cause Analysis:**
  The pre-existing `manifest.json` and `manifest.csv` files stored in `data/reference_library/` contained 169 absolute local Windows filesystem paths (`C:\Users\Admin\...`). When deployed inside the Linux container (`/app`), path lookups for `Path(asset["processed_path"]).exists()` evaluated to `False`.
- **Remediation Completed Locally (Commit `6608f24`):**
  1. Updated `backend/app/services/reference_library.py` to add `_normalize_asset_paths()`. When loaded into memory, any absolute path that does not exist on the current filesystem is dynamically rebound to the relative runtime reference directory (`REF_PROC_DIR`, `REF_SPEC_DIR`, etc.).
  2. Updated `backend/app/routers/communicate.py` audio and media endpoints with a secondary lookup fallback to `REF_PROC_DIR / Path(raw_p).name`.
  3. Ran all 99 tests locally; all passed.
- **Resolution Path:**
  Once commit `6608f24` is pushed to GitHub `origin/main`, Render's webhook will automatically deploy the fix.

---

## 8. Remaining Owner Actions

To bring the entire deployment to 100% turnkey production readiness, the repository owner must perform the following three actions:

### 1. Push Local Remediated Commit `6608f24` to GitHub
- **Why Required:** The local Git credential cache on this development workstation belongs to user `uk7103563-spec`, while the remote repository `https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity.git` is owned by `sanjaykiran645-beep`. Pushing from this machine encountered HTTP 403 Forbidden.
- **Owner Action:** In terminal, execute:
  ```powershell
  git push origin main
  ```
  *(Or alternatively, add `uk7103563-spec` as a collaborator with write access on the GitHub repository).*
- **Effect:** Triggers an automatic Render deployment, resolving the Engine B reference audio streaming (Test 10).

### 2. Redeploy the GitHub Pages Frontend
- **Why Required:** The static bundle currently published to GitHub Pages was compiled prior to knowing the cloud backend address.
- **Owner Action:** In `frontend/`, compile and publish the latest build:
  ```powershell
  cd frontend
  npm install
  npm run build
  # Deploy dist/ to gh-pages branch or trigger GitHub Action
  ```
  *(In the meantime, users can immediately connect by entering `https://caninesense-backend.onrender.com` in `#/app/settings` under "FastAPI Backend Origin URL").*

### 3. Provision Persistent Storage on Render (For Production Persistence)
- **Why Required:** To preserve user accounts, dog profiles, and uploaded recordings across container spin-downs or redeployments.
- **Owner Action:**
  1. In the Render Dashboard (`https://dashboard.render.com/web/srv-dbq9o9m7bikc73dctmq0`), upgrade instance type to **Starter** ($7/mo).
  2. In **Disks**, add a 1GB Persistent Disk mounted at `/var/caninesense_data`.
  3. In **Environment**, set `CANINESENSE_DATA_DIR=/var/caninesense_data`.
  4. Redeploy.

---

## 9. Final Conclusion & Production Reality Statement

CanineSense AI has successfully graduated from a mock frontend prototype to a live, cloud-hosted, full-stack bioacoustic application. The actual FastAPI backend, Engine A machine learning inference, bcrypt authentication, and GDPR-compliant data isolation are operational on Render at `https://caninesense-backend.onrender.com`.

Full turnkey production status will be achieved upon pushing commit `6608f24` and attaching persistent storage as documented above.
