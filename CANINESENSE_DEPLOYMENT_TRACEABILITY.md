# CanineSense AI — Deployment & Commit Traceability Report

**Date:** 2026-11-18  
**GitHub Repository:** `https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity`  
**GitHub Pages URL:** `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/`  
**Render Service:** `caninesense-backend` (`srv-dbq9o9m7bikc73dctmq0`, Oregon, Free Tier, Docker)  
**Render URL:** `https://caninesense-backend.onrender.com`

---

## 1. Source-to-Production Commit Traceability Matrix

| Target Environment | Pre-Audit State (Observed Start) | Intermediate Release (2026-11-18) | Final Verified State (2026-11-18) | Status |
|---|---|---|---|---|
| **Local `main`** | `b8fc3eba889c29ee859d5c558e0e545e0ab11c63` (2026-11-16) | `61f614a1d88ad23bf6b5d5dc80afe65ae5e392af` | **`a53e5c13335376be20eb60903bf71904dd8c94ac`** | **PASS** |
| **GitHub `origin/main`** | `b8fc3eba889c29ee859d5c558e0e545e0ab11c63` | `61f614a1d88ad23bf6b5d5dc80afe65ae5e392af` | **`a53e5c13335376be20eb60903bf71904dd8c94ac`** | **PASS** |
| **GitHub Pages (`origin/gh-pages`)** | `3c5627da339997a4e7835b41d5e636c13fadc356` (2026-11-12, `index-9QZd7XTz.js`) — **14 commits behind** | `d18162458183f76138b8fd329bd66e3d215158b5` (`index-CJZuRqPb.js`) | **`07d639439514606db5cf1011ee356e8366f3c614`** (`index-CJAKXIuV.js`, `index-u4mLwK6I.css`) | **PASS** |
| **Render (`caninesense-backend`)** | `dep-dbqte715efls73ahlj80` / commit `c29a13082d48139b6339ebf42cad2cdb6b687c6b` (2026-11-12) — **14 commits behind** (`/api/experiments/metrics` returned 404) | `dep-dbukauk9v7es738rbvh0` (`61f614a1`) | **`dep-dbukjn4ipgvc7397btig`** (status `live`, commit **`a53e5c13335376be20eb60903bf71904dd8c94ac`**, 51 OpenAPI routes) | **PASS** |
| **Android APK (`CanineSense_AI_v1.0.0.apk`)** | Built `2026-11-07T16:08:46+05:30`, SHA-256 `E17BD6DD6221DDB2A78E99817355BCA409F2F6945910F4BEC854585686AA34AC` (`index-B_fOKfw7.js`) | Unchanged | Unchanged (**OBSOLETE**; rebuild **BLOCKED** — no JDK/Android SDK on host) | **BLOCKED** |

---

## 2. Live Deployment Verification Details

1. **GitHub Pages Verification:**
   - `GET https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/` returned HTTP 200 (1,362 bytes) referencing `./assets/index-CJAKXIuV.js` and `./assets/index-u4mLwK6I.css`, with relative `./favicon.svg` and `./manifest.webmanifest`.
   - Service Worker `sw.js` uses `caninesense-shell-v2` with network-first navigation and zero `/api/` caching.
2. **Render Verification:**
   - `GET https://caninesense-backend.onrender.com/api/health` returned HTTP 200 (`status: "ok"`, `ffmpeg_available: true`, `soundfile_wav: true`, `accuracy_target_met: false`).
   - `GET https://caninesense-backend.onrender.com/api/openapi.json` confirmed 51 active routes including `/api/experiments/metrics`.
   - `Origin: https://sanjaykiran645-beep.github.io` confirmed `Access-Control-Allow-Origin: https://sanjaykiran645-beep.github.io`.
   - Live Engine A recording upload (`1_Stranger_Alert_High_Bark_410Hz.wav`) and Engine B synthesis (`7f2db50b-8c20-4cea-8a4d-440a618bca47`) both executed against Render and persisted cleanly; synthetic test user was then erased via `DELETE /api/account`.
3. **Persistence Warning:**
   - Render service `srv-dbq9o9m7bikc73dctmq0` runs on `plan: free` without a Render Persistent Disk. SQLite (`/app/data/caninesense.sqlite3`) and `/app/data/storage` are ephemeral across redeploys and container restarts.
4. **Docker Image Digest:**
   - Render builds directly from `./Dockerfile` in GitHub commit `a53e5c13335376be20eb60903bf71904dd8c94ac` using Render's internal registry; no external Docker Hub digest is exposed via Render CLI.
