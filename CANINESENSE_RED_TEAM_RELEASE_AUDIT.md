# CanineSense AI — Red-Team Release Audit

**Audit Date:** 2026-11-18  
**Project Root:** `E:\CanineSense_AI_Complete_Project (1)\CanineSense_AI`  
**Final Verified Source Commit (`main` / `origin/main`):** `a53e5c13335376be20eb60903bf71904dd8c94ac`  
**Frontend Deployment Commit (`gh-pages` / `origin/gh-pages`):** `07d639439514606db5cf1011ee356e8366f3c614` (`assets/index-CJAKXIuV.js`, `assets/index-u4mLwK6I.css`)  
**Backend Deployment (`caninesense-backend` / Render `srv-dbq9o9m7bikc73dctmq0`):** `dep-dbukjn4ipgvc7397btig` (`status: live`, commit `a53e5c13335376be20eb60903bf71904dd8c94ac`)  
**Docker Image Digest:** N/A (Render managed Dockerfile build from commit `a53e5c13335376be20eb60903bf71904dd8c94ac`)  
**Android APK Version & Hash:** `v1.0.0` (`versionCode 1`, `122,203` bytes), SHA-256 `E17BD6DD6221DDB2A78E99817355BCA409F2F6945910F4BEC854585686AA34AC` (**OBSOLETE** — built `2026-11-07T16:08:46+05:30`, rebuild **BLOCKED** due to absent JDK/Android SDK on host)

---

## 1. Release Gate Summary

### A. Software Engineering Release Gate: **PASS (`SOFTWARE RELEASE VERIFIED` for Web & Backend)**

| Gate | Status | Evidence |
|---|---|---|
| **Frontend Production Build (`tsc -b && vite build`)** | **PASS** | 0 TypeScript errors, 0 Vite build errors (`index-CJAKXIuV.js` 471.94 kB, `index-u4mLwK6I.css` 30.42 kB) |
| **Frontend Lint (`oxlint`)** | **PASS** | Exit 0 (0 errors, 33 warnings across 35 files) |
| **Backend Full `pytest` Suite** | **PASS** | **143 passed, 0 failed, 0 skipped** (116.29s) |
| **Priority 8 Communicator Audio Matrix** | **PASS** | **23 passed, 0 failed, 0 skipped** (34.63s) |
| **Priority 7 Behavioural Validation Lab Suite** | **PASS** | **11 passed, 0 failed, 0 skipped** (19.83s) |
| **Security-Critical Test Suite** | **PASS** | **13 passed, 0 failed, 0 skipped** (41.23s) |
| **Live Production Browser Acceptance (Desktop + `390x844` Mobile)** | **PASS** | All pages rendered cleanly with 0 console errors, 0 failed HTTP requests, live Render Engine A + Engine B verified, Validation Lab 5 tabs verified, mobile overflow fixed |
| **Deployment Commit Traceability** | **PASS** | `main`, `origin/main`, Render `dep-dbukjn4ipgvc7397btig`, and `gh-pages` (`07d6394`) all trace directly to `a53e5c13335376be20eb60903bf71904dd8c94ac` |
| **Android APK Binary Release** | **BLOCKED** | Packaged `CanineSense_AI_v1.0.0.apk` is from Nov 7 (`index-B_fOKfw7.js` + 112-byte `classes.dex`); host lacks JDK (`javac`) and Android SDK/Gradle to rebuild |

### B. Scientific Validation Gate: **SEPARATE & NOT MET**

| Scientific Domain | Status | Verified Facts |
|---|---|---|
| **Engine A (Dog → Human 90% Gate)** | **FAIL** | Reproduced via `scripts/reproduce_engine_a_eval.py`: **85.46% balanced accuracy** (86.81% overall accuracy, 78.77% macro F1, ECE 0.1440, Brier 0.1481) across 91 held-out test files (26 test dog clusters vs 45 train dog clusters, 0 overlap). Short of 90.00% target by **4.54 percentage points**. |
| **Engine B (Human → Dog Biological Validation)** | **NOT VALIDATED** | **0** live canine behavioral trials performed; **0.0%** empirically verified target congruence. DSP synthesis and protocol software are Maturity Level 4; biological efficacy is Maturity Level 1. |
| **Breed & Sex Acoustic Scaling** | **HEURISTIC** | Allometric body-mass estimates and male (`x0.91`) / female (`x1.08`) multipliers are unvalidated priors, not clinically certified measurements. |

---

## 2. File-by-File Red-Team Audit Totals

Automated scan via `scripts/CanineSense-RedTeam-Audit.ps1` (`RED_TEAM_AUDIT.json`) audited **630** project files (excluding `.git`, `node_modules`, `dist`, `__pycache__`, `.pytest_cache`):

| Classification | Count | Notes |
|---|---:|---|
| `PASS` | 608 | Verified source, test, data, manifest, and config files |
| `DUPLICATE` | 17 | `data/releases/CanineSense_AI_v1.0.0.apk` + 16 root/docs mirrored reports (`engine_b_action_taxonomy.md` differs between root and `docs/`) |
| `REQUIRES OWNER INPUT` | 2 | `.env` (local secret config, ignored by `.gitignore`), `frontend/.env.production` |
| `DEFECTIVE` | 1 | `render.yaml` (`plan: free` has no persistent disk; requires owner decision before upgrading to a paid plan) |
| `SECURITY RISK` | 1 | `backend/app/routers/experiments.py` (`submit_independent_review` hides `primary_observer_category` in blind mode, but relies on trial UUID secrecy rather than an explicit reviewer invite table) |
| `OBSOLETE` | 1 | `CanineSense_AI_v1.0.0.apk` (Nov 7 build; Android SDK unavailable on host to rebuild) |
| `MISSING` | 0 | (Note: `.github/workflows` directory is absent — external/scripted deployment used instead) |
| `UNUSED` | 0 | Preserved per non-destructive retention rules |

---

## 3. Defects Found & Remediated During This Audit

1. **GitHub Pages Static Host API Routing Failure (`frontend/src/api.ts`) — FIXED:** `getBackendUrl()` previously ignored `import.meta.env.VITE_API_URL` and stripped `onrender.com` from `localStorage`, causing API calls on `sanjaykiran645-beep.github.io` to hit GitHub Pages instead of Render. Repaired to route `github.io` and Capacitor native shells to `VITE_API_URL` (`https://caninesense-backend.onrender.com`) while keeping `localhost` on `window.location.origin` (Vite proxy) and Render self-hosted SPA on `window.location.origin`.
2. **Corrupted `localStorage` Crash & Broken Offline Demo Button (`frontend/src/api.ts`) — FIXED:** Wrapped `getUser()` `JSON.parse` in `try/catch` and restored `isDemoSession()` to match explicit `cs_demo_token_offline_preview` sessions (without allowing auth routes to mock).
3. **Behavioural Validation Lab Production Crash (`frontend/src/pages/ValidationLab.tsx` & `backend/app/services/trial_service.py`) — FIXED:** Live browser testing caught `TypeError: Cannot read properties of undefined (reading 'correct_action_rate')` when `GET /api/experiments/metrics` returned minimal `{ status: "insufficient_data" }` for zero trials. Repaired both backend zero-trial schema and frontend optional-chaining guards; added `test_empty_experimental_metrics_schema_complete`.
4. **Priority 7 Runtime Crash & Cross-Tenant FK Gaps (`backend/app/routers/experiments.py`) — FIXED:** Added missing `secrets` import (`random.randint` previously raised `NameError` HTTP 500 when `randomization_seed` was omitted), added ownership checks on `dog_id`, `cue_id`, and `schedule_id`, committed `audit.log` inside the participant transaction, and suppressed `primary_observer_category` in blind review responses. Added `test_schedule_without_seed_and_cross_tenant_fk_isolation`.
5. **Account Erasure Completeness (`backend/app/routers/analytics.py`) — FIXED:** `delete_account` now explicitly purges `TrialIndependentReview`, `BehaviouralTrial`, `TrialSchedule`, `ExperimentalCue`, and `StudyParticipant` rows. Added `test_account_delete_erases_priority7_experimental_records`.
6. **Engine A Upload Timeout on Cloud Backend (`frontend/src/pages/Analyze.tsx`) — FIXED:** Increased upload fetch abort timeout from 3.5s to 30s so Render server-side `/api/recordings/quick-analyze` completes reliably (verified end-to-end on live Render with `1_Stranger_Alert_High_Bark_410Hz.wav`).
7. **Mobile `390x844` Horizontal Overflow & Dark Theme Header Contrast (`frontend/src/index.css`, `Communicate.tsx`, `Dashboard.tsx`) — FIXED:** Eliminated `minWidth` overflows and added responsive header/card containment plus high-contrast pill backgrounds for `white-black`, `red-blue`, and `yellow-green` themes. Re-verified in live browser at `390x844` (`374.67px <= 390px`).
8. **GitHub Pages Subpath Icons & Dashboard Mojibake (`frontend/index.html`, `Dashboard.tsx`) — FIXED:** Switched `/favicon.*` and `/manifest.webmanifest` to `./` relative paths; replaced `?` mojibake with `→`, `·`, and `’`.
9. **Android Cleartext Flag (`mobile-android/android/app/src/main/AndroidManifest.xml`) — FIXED:** Changed `android:usesCleartextTraffic` from `"true"` to `"false"`.

---

## 4. Remaining Open Blockers & Recommendations

1. **Render Free-Tier Ephemeral Disk (`RT-DEP-01` — HIGH):** `render.yaml` uses `plan: free` without a persistent disk. Any Render redeploy or container restart wipes `/app/data/caninesense.sqlite3`, user uploads, and `.secret`. Adding a persistent disk requires upgrading to a paid Render plan (owner approval required per Rule 14).
2. **Obsolete Android APK (`RT-MOB-02` — HIGH / BLOCKED):** `CanineSense_AI_v1.0.0.apk` must be rebuilt with `npm run build:android` + Gradle in an environment with JDK 17+ and Android SDK 34.
3. **Missing `.github/workflows` (`RT-INFRA-01` — MEDIUM):** Consider adding CI/CD workflows for automated pytest, Vite build, and `gh-pages` deployment.
4. **Blind Reviewer Assignment Scoping (`RT-SEC-01` — MEDIUM):** Introduce an explicit reviewer invitation/assignment table for `POST /api/experiments/trials/{trial_id}/reviews` so authorization does not rely solely on trial UUID secrecy.
5. **Scientific Validation (Unmet Gates):** Collect real multi-breed, multi-dog field recordings for Engine A to close the 4.54% balanced-accuracy gap, and conduct pre-registered controlled trials with live dogs for Engine B.

---

## 5. Rollback Instructions

* **Source (`main`):** Pre-audit `main` was `b8fc3eba889c29ee859d5c558e0e545e0ab11c63`. To revert without rewriting history, run `git revert --no-edit b8fc3eba889c29ee859d5c558e0e545e0ab11c63..HEAD` and push fast-forward to `origin/main`.
* **GitHub Pages (`gh-pages`):** Pre-audit `gh-pages` was `3c5627da339997a4e7835b41d5e636c13fadc356`. Check out `gh-pages`, restore tree from `3c5627da`, commit, and push fast-forward.
* **Render Backend (`srv-dbq9o9m7bikc73dctmq0`):** In Render Dashboard or CLI, run `render deploys create srv-dbq9o9m7bikc73dctmq0 --commit b8fc3eba889c29ee859d5c558e0e545e0ab11c63 --confirm` (or `c29a13082d48139b6339ebf42cad2cdb6b687c6b` for Nov 12 baseline).
