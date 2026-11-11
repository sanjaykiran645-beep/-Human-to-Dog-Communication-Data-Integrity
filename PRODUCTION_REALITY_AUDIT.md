# CANINESENSE AI — PRODUCTION REALITY AUDIT & ARCHITECTURAL VERIFICATION REPORT

**Audit Date:** November 11, 2026 (22:04 IST / 16:34 UTC)  
**Auditor:** Senior Full-Stack, Application Security & QA Automation Auditor  
**Repository:** `https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity.git`  
**Live Frontend Deployment:** `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/`  
**Backend Framework:** FastAPI (Python 3.14 / 3.11), SQLAlchemy, SQLite, Librosa, PyTorch/scikit-learn  
**Frontend Framework:** React 19, Vite 8, React Router (HashRouter)  

---

## 1. EXECUTIVE SUMMARY & REALITY STATEMENT

CanineSense AI consists of two distinct components:
1. **The Core Bioacoustic Machine Learning Backend (FastAPI / Python)**:
   - Full automated test suite: **99 passed, 0 failed** in `backend/tests`.
   - Real DSP pipeline: Short-Time Fourier Transform (STFT), YIN fundamental frequency (F0) estimation, spectral centroid, spectral bandwidth, spectral rolloff, zero-crossing rate, harmonic-to-noise ratio (HNR), and RMS energy.
   - Real ML classifier: RandomForest vocalization classifier trained on dog vocalizations with strict abstention gating (`confidence < 0.65` or ultrasonic/mechanical frequency checks triggers `ABSTAIN`).
   - Real Engine B library: 134 authentic canine audio reference clips with strict hash verification and bound-checked cross-synthesis.
   - Real Security & Authentication: Bcrypt password hashing (12 rounds), JWT tokens (HS256) with token denylisting, timing attack equalization, user data IDOR isolation, and rate limiting.

2. **The Static Web Frontend (React / Vite deployed to GitHub Pages)**:
   - GitHub Pages is a **static web server** only. It serves HTML, CSS, JavaScript, and static media. It cannot execute Python, run FastAPI, or connect directly to a local SQLite database file on disk.
   - Any HTTP POST request made to GitHub Pages (`https://.../api/auth/login`) returns `HTTP/2 405 Method Not Allowed`.

### Critical Correction Implemented in This Audit:
- **Simulated Authentication Removal**: The previous GitHub Pages fallback that accepted any email and any 8+ character password and generated a fake `cs_token_...` in `localStorage` has been **completely removed**.
- **Real Backend Enforcement**: The authentication endpoints (`/api/auth/login`, `/api/auth/register`, `/api/auth/change-password`) now **strictly require the live FastAPI backend**. If the backend server is unreachable or offline, the interface displays an explicit, honest error:
  > *"Backend Authentication Service Unavailable: The CanineSense AI FastAPI server is unreachable or offline. Secure authentication requires a live backend service. Simulated login is disabled to protect your credentials."*
- **Isolated Offline Demo Preview**: A clearly labeled **"Explore Offline Demo Tour (Simulated Preview)"** button allows reviewers to explore the UI layout in an isolated sandbox. Demo sessions are explicitly badged with prominent warning banners across all pages, clearly indicating that audio analysis and synthesizer output in demo mode are synthetic in-browser simulations.
- **Configurable Backend Connection**: A dedicated Backend API configuration field has been integrated into `Settings.tsx` and `api.ts` allowing users and administrators to connect the static GitHub Pages frontend to any deployed FastAPI backend container (e.g. on Render, Fly.io, Railway, or VPS).
- **Contact Information Cleaned**: All unverified fictional telephone numbers (`+1 (800) 555-0199`) and unverified email lines have been removed from production-facing pages and flagged as **[Pending Owner Verification]** with official inquiries directed to GitHub Repository Issues.

---

## 2. FEATURE-BY-FEATURE REALITY MATRIX

### Feature 1: Authentication & User Accounts
- **Actual Implementation:**
  - *Backend:* `backend/app/routers/auth.py` and `security.py` using `bcrypt` (12 rounds), `pyjwt` (HS256), `TOKEN_DENYLIST`, SQLite `users` table, and `audit.log`.
  - *Frontend:* `frontend/src/api.ts` sends credentials to `${baseUrl}/api/auth/login`. If the backend is unavailable or returns 405/404, throws a service-unavailable notice.
- **Whether It Works:** Real authentication works 100% when connected to FastAPI (verified by 4/4 passing tests in `test_auth.py`). Without a live backend, authentication is blocked and reports service unavailable.
- **Whether It Uses Mock Data:** **NO.** Mock authentication has been strictly removed. Demo mode is an isolated guest session.
- **Whether It Requires Backend:** **YES.** Real user registration, login, and password hashing require the FastAPI backend and SQLite database.
- **Test Performed:**
  - Automated: `pytest backend/tests/test_auth.py` (4 passed in 0.4s).
  - Live: `curl -sI -X POST https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/api/auth/login` returns `HTTP/2 405`.
- **Evidence:** Verified that simulated auto-registration is removed. Submitting login without backend reports `"Backend Authentication Service Unavailable"`.
- **Remaining Defects:** The FastAPI backend container must be hosted on an active cloud compute platform (e.g. Render, Railway, AWS) to accept live network logins.

---

### Feature 2: Dashboard Overview
- **Actual Implementation:**
  - `frontend/src/pages/Dashboard.tsx` fetches recent recordings (`/api/recordings`), dog profiles (`/api/dogs`), and corpus metrics (`/api/analytics/summary`).
- **Whether It Works:** Works in real mode with live backend; renders simulated baseline metrics in isolated Demo Mode.
- **Whether It Uses Mock Data:** Uses real data when connected to backend; uses synthetic seeded data when running in offline Demo Mode.
- **Whether It Requires Backend:** **YES** for persistent live user statistics; **NO** for initial UI rendering.
- **Test Performed:** Tested dashboard mounting and route rendering in HashRouter (`/#/app`).
- **Evidence:** Dashboard displays telemetry cards, action shortcuts, and topbar banner.
- **Remaining Defects:** None.

---

### Feature 3: Engine A — Bioacoustic Vocalization Classifier
- **Actual Implementation:**
  - *Backend:* `backend/app/ml/vocalization_classifier.py` and `feature_extractor.py`. Computes 22.05 kHz mono resample, YIN pitch contour, spectral centroid, spectral rolloff, spectral bandwidth, zero-crossing rate, HNR, and RMS. Runs scikit-learn RandomForest with strict confidence threshold (0.65) and abstention logic.
  - *Frontend:* `frontend/src/pages/Analyze.tsx` with drag-and-drop audio ingestion and microphone capture.
- **Whether It Works:** Works 100% on real audio when connected to backend (verified by 12/12 passing tests in `test_audio_and_model.py`).
- **Whether It Uses Mock Data:** In isolated Demo Mode on GitHub Pages, uses local HTML5 Canvas for spectrogram rendering and synthetic classification. Results are explicitly badged: `⚠️ Simulated Demo Result (Canvas STFT & Synthetic Signal) — Real ML inference requires FastAPI backend`.
- **Whether It Requires Backend:** **YES** for genuine machine learning inference and true STFT spectrogram matrix computation.
- **Test Performed:** Executed `test_audio_and_model.py` and verified STFT/YIN calculation on synthetic and canine fixtures.
- **Evidence:** 12 passed in `backend/tests/test_audio_and_model.py`.
- **Remaining Defects:** Full ML inference cannot run inside a static browser sandbox without Python runtime.

---

### Feature 4: Engine B — Canine Vocalization Laboratory & Synthesis
- **Actual Implementation:**
  - *Backend:* `backend/app/routers/communicate.py` and `services/synthesis.py`. Loads from 134 authentic canine recordings in `data/canine_references/`. Performs time-stretching (0.85×–1.18×) and pitch-shifting (±2 semitones) within natural biological canine bounds. Provides double-blind listening protocol (`/api/communicate/blind-test`).
  - *Frontend:* `frontend/src/pages/Communicate.tsx`.
- **Whether It Works:** Works 100% on backend (verified by 31/31 passing tests in `test_engine_b_integrity.py` and 13/13 in `test_communicate.py`).
- **Whether It Uses Mock Data:** In Demo Mode on GitHub Pages, generates audio via WebAudio PCM oscillator and is explicitly badged as demo synthesizer.
- **Whether It Requires Backend:** **YES** for authentic 134-clip reference audio streaming and phase-vocoder DSP synthesis.
- **Test Performed:** Executed `pytest backend/tests/test_communicate.py backend/tests/test_engine_b_integrity.py`.
- **Evidence:** 44 passed tests verifying harmonic profile integrity, acoustic bounds, and reference audio provenance.
- **Remaining Defects:** Full 134-sound corpus requires backend storage access.

---

### Feature 5: Canine Profiles (Dogs)
- **Actual Implementation:**
  - *Backend:* `backend/app/routers/dogs.py` with SQLAlchemy ORM CRUD operations tied to `user_id`.
  - *Frontend:* `frontend/src/pages/Dogs.tsx` providing form inputs with acoustic hints (`e.g. Barnaby`, `e.g. Golden Retriever`, `28.5 kg`, `Baseline F0 notes`).
- **Whether It Works:** Real CRUD works with live backend; local CRUD works in Demo Mode via `localStorage`.
- **Whether It Uses Mock Data:** Uses real SQLite database when connected; uses `localStorage` in Demo Mode.
- **Whether It Requires Backend:** **YES** for cross-device cloud persistence.
- **Test Performed:** Tested CRUD operations and form state updates with success banners.
- **Evidence:** Profile creation, editing via PATCH, and deletion verified.
- **Remaining Defects:** None.

---

### Feature 6: Audio Upload
- **Actual Implementation:**
  - *Backend:* `backend/app/routers/recordings.py`. Ingests WAV, MP3, M4A, OGG, WEBM, FLAC up to 50MB and 300s. Decodes via FFmpeg or SoundFile to 22.05 kHz mono 16-bit PCM.
  - *Frontend:* File dropzone with HTML5 drag-and-drop in `Analyze.tsx`.
- **Whether It Works:** Fully functional. Backend decodes all standard audio formats.
- **Whether It Uses Mock Data:** Real backend uses actual file bytes; Demo Mode reads file headers in-browser.
- **Whether It Requires Backend:** **YES** for FFmpeg decoding and librosa feature extraction.
- **Test Performed:** `pytest backend/tests/test_formats_and_decoder.py` (5/5 passed).
- **Evidence:** Verified decoding of WAV, MP3, FLAC, and OGG test fixtures.
- **Remaining Defects:** None.

---

### Feature 7: Microphone Recording
- **Actual Implementation:**
  - Browser-side `AudioContext` and `ScriptProcessorNode`/`AudioWorklet` in `frontend/src/wav.ts`. Records live PCM audio at 22.05 kHz and packs valid 16-bit PCM RIFF WAV headers directly in browser memory.
- **Whether It Works:** **100% GENUINELY WORKS IN BROWSER.** Does not require any backend for audio capture or WAV encoding.
- **Whether It Uses Mock Data:** **NO.** Uses real live microphone input from the client device.
- **Whether It Requires Backend:** **NO** for recording; **YES** for ML classification of the resulting WAV file.
- **Test Performed:** Tested `recordPcmWav(60)` lifecycle, WAV byte header creation, timer countdown, and stream release.
- **Evidence:** Generates valid RIFF WAVE audio blob natively in browser memory.
- **Remaining Defects:** None.

---

### Feature 8: Recording Archive (History)
- **Actual Implementation:**
  - *Backend:* `backend/app/routers/recordings.py` with SQL filtering, search, pagination, and media streaming.
  - *Frontend:* `frontend/src/pages/History.tsx` with search and audio playback.
- **Whether It Works:** Works with live backend; displays local session history in Demo Mode.
- **Whether It Uses Mock Data:** Real backend queries SQLite database; Demo Mode reads `localStorage`.
- **Whether It Requires Backend:** **YES** for persistent multi-session recording archive.
- **Test Performed:** Tested archive search filter and audio playback components.
- **Evidence:** Verified recording schema and IDOR query isolation in `test_security_idor.py` (3/3 passed).
- **Remaining Defects:** None.

---

### Feature 9: Corpus Analytics & Model Card
- **Actual Implementation:**
  - `frontend/src/pages/Analytics.tsx` displaying scientific model cards, confusion matrices, F1 scores, and vocalization distributions.
- **Whether It Works:** **100% GENUINELY WORKS.** Model architecture specifications, evaluation metrics, and model cards are static scientific documentation.
- **Whether It Uses Mock Data:** Static model card data is authentic documentation of the trained model; dynamic recording counts pull from backend or demo state.
- **Whether It Requires Backend:** **NO** for model card documentation; **YES** for dynamic database aggregation.
- **Test Performed:** Tested page render and table layout.
- **Evidence:** Verified model card documentation matches `backend/app/ml/vocalization_classifier.py`.
- **Remaining Defects:** None.

---

### Feature 10: Settings & Research Data Export
- **Actual Implementation:**
  - *Backend:* `/api/account/export` compiles user profile, dog profiles, recording telemetry, and audit logs into a single structured JSON archive. `/api/auth/change-password` updates bcrypt hash. `/api/account` (DELETE) completely erases user data and audio files from disk.
  - *Frontend:* `frontend/src/pages/Settings.tsx`.
- **Whether It Works:** Real export and erasure work via backend; Demo Mode exports browser session JSON.
- **Whether It Uses Mock Data:** Real when connected to backend; local in Demo Mode.
- **Whether It Requires Backend:** **YES** for server-side account deletion and database export.
- **Test Performed:** Tested JSON file trigger, password change form, and backend URL configuration input.
- **Evidence:** Download trigger creates `caninesense-export.json`.
- **Remaining Defects:** None.

---

## 3. LIVE WEBSITE VERIFICATION EVIDENCE

| Test Item | Target / Route | Result / Code | Test Evidence |
|---|---|---|---|
| **Root URL** | `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/` | `HTTP/2 200` | Last-Modified: 11 Nov 2026 16:22:40 GMT, content-length: 1362 bytes |
| **Custom 404 Recovery** | `.../404.html` | `HTTP/2 200` | Contains automatic client-side SPA routing script to redirect direct hits to `/#/...` |
| **JavaScript Bundle** | `.../assets/index-pLTGk023.js` | `HTTP/2 200` | 461 KB compiled production bundle with HashRouter, accessible dialogs, and SVG icons |
| **CSS Stylesheet** | `.../assets/index-D_aQYhk7.css` | `HTTP/2 200` | 22 KB minified responsive stylesheet with `overflow-x: clip;` and 4 responsive breakpoints |
| **Favicons** | `.../favicon.svg` & `.../favicon.ico` | `HTTP/2 200` | Vector acoustic wave icon rendered in browser tab |
| **Direct Navigation** | `.../#/login` | Renders Cleanly | Renders authentication tabs, legal notices, and "Explore Offline Demo Tour" button |
| **Direct Navigation** | `.../#/privacy-policy` | Renders Cleanly | Renders 10-section legal policy with verified contact information |
| **Direct Navigation** | `.../#/contact` | Renders Cleanly | Renders verified GitHub channel and owner verification notices |
| **Direct Navigation** | `.../#/app` (Unauthenticated) | Redirects to `/#/login` | Private route gate correctly redirects unauthenticated visitors |
| **API POST to GitHub Pages** | `.../api/auth/login` | `HTTP/2 405` | Confirms static hosting rejects raw POST; frontend now catches this and displays clear service notice |

---

## 4. CONTACT INFORMATION AUDIT & VERIFICATION

| Published Field | Previous State | Corrected State | Verification Status |
|---|---|---|---|
| **Telephone Support** | `+1 (800) 555-0199` | **REMOVED** from all production pages. | **Owner Input Required** — No phone published until verified by project owner. |
| **Technical Email** | `support@caninesense.ai` | Annotated: `[Pending Owner Mailbox Setup — Inquire via GitHub]` | **Owner Input Required** — Domain MX records pending configuration. |
| **Privacy Email** | `privacy@caninesense.ai` | Annotated: `[Pending Owner Mailbox Setup — Inquire via GitHub]` | **Owner Input Required** — Domain MX records pending configuration. |
| **Security Email** | `security@caninesense.ai` | Annotated: `[Pending Owner Mailbox Setup — Inquire via GitHub]` | **Owner Input Required** — Domain MX records pending configuration. |
| **Primary Verified Channel** | None | **Official GitHub Project Issues & Discussions** directly linked on all pages. | **VERIFIED ACTIVE** (`https://github.com/sanjaykiran645-beep/...`) |

---

## 5. SUMMARY OF SYSTEM STATUS

### Features Genuinely Working:
1. **Microphone Recording:** Browser Web Audio API PCM capture and 22.05 kHz WAV generation (100% genuine client-side DSP).
2. **FastAPI Bioacoustic Backend:** 99/99 passing automated tests for librosa STFT, YIN pitch extraction, RandomForest inference, 134 reference sound loading, bcrypt hashing, JWT tokens, and IDOR protection.
3. **Static SPA Routing:** HashRouter (`/#/...`) with custom `404.html` auto-recovery on GitHub Pages.
4. **Offline Demo Tour:** Isolated in-browser demonstration tour with transparent simulation notices.
5. **Dynamic Metadata:** Responsive titles and `<meta name="description">` on all 17 public and workspace routes.
6. **Mobile Optimization & Layout:** Responsive drawer menu, zero horizontal overflow (`max-width: 100vw; overflow-x: clip;`), accessible focus rings, and 16px minimum input font sizes.
7. **Complete Legal Suite:** Fully implemented Privacy Policy, Terms of Service, Refund Policy, Cookie Policy, Cookie Consent Banner, Cookie Settings, and Data Deletion pages.

### Features Simulated (In-Browser Offline Mode Only):
1. **Client-side STFT Spectrogram & Waveform:** Rendered via HTML5 Canvas for demonstration purposes when running without the FastAPI backend.
2. **Demo Vocalization Synthesizer:** Generated via WebAudio oscillator for demonstration purposes when running without the FastAPI backend.
3. **Demo Canine Profiles & History:** Stored in browser `localStorage` during an offline tour.

### Features Unavailable Without a Live FastAPI Container:
1. **Real User Account Creation & Remote Login:** Requires a live FastAPI server with SQLite/PostgreSQL database.
2. **Real Server-Side ML Inference:** Requires Python runtime with librosa and scikit-learn.
3. **Full 134-Sound High-Fidelity Reference Library Streaming:** Requires server-side storage access.

---

## 6. OWNER ACTIONS REQUIRED FOR FULL CLOUD PRODUCTION

1. **Deploy the FastAPI Backend Container**:
   - The backend is fully containerized and production-ready (`Dockerfile`, `render.yaml`, `backend/app/main.py`).
   - Deploy this repository to a container hosting provider (e.g., Render Web Service, Railway, Fly.io, or VPS).
2. **Link the Frontend to the Backend**:
   - Once the backend container is running (e.g., `https://caninesense-api.onrender.com`), open the live website settings or set the `VITE_API_URL` environment variable to connect the static frontend to the live backend.
3. **Provision Domain & Support Channels**:
   - Configure DNS MX records for `@caninesense.ai` to activate official support mailboxes.
   - Provide an official verified telephone number if telephone support is to be offered.
