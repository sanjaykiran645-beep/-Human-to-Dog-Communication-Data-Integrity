# CanineSense AI — Phase 14 Deployment Traceability & Baseline Reconciliation

**Timestamp (UTC):** 2026-11-18T15:35:00Z  
**Script Executed:** `CanineSense-Phase14-Deployment.ps1`, `CanineSense-Release-Verify.ps1 -CheckLiveProduction` (`logs/phase14-deployment.json`, `logs/latest-release-verify.json`)

---

## 1. Source-to-Production Mapping

| Component | Source Commit | Build Artifact / Version | Live Deployment Target | Status |
|---|---|---|---|---|
| **Frontend SPA** | `cce101d73cce52cbecac71155c8ffed2f169bfce` (UI source unchanged in `44984caa`) | `frontend/dist/assets/index-D49uE4oN.js` (`481.34 kB`), `index-u4mLwK6I.css` (`30.42 kB`) | GitHub Pages `gh-pages` commit `3c866a9954504c07e600ae560d8c585062a218d5` | **PASS (LIVE)** |
| **Backend API** | `44984caa44720212c3ab064eca0885b8a94193c7` (`main`) | Docker multi-stage build (`Dockerfile`, `python:3.12-slim-bookworm`, `58` OpenAPI routes) | Render `srv-dbq9o9m7bikc73dctmq0` deploy `dep-dbus42jm8hqs73b8jj7g` (`status: live`, `15:20:49Z`) | **PASS (LIVE)** |
| **Android APK** | `588324dc` / `44984caa` (`network_security_config.xml`) | Existing `CanineSense_AI_v1.0.0.apk` (`2026-11-07`, `122,203` bytes, SHA-256 `E17BD6DD...`) | Served at `/api/download/apk` (obsolete relative to live web/API) | **BLOCKED (Toolchain Missing)** |
| **Database Schema** | `backend/app/db.py` (`_MIGRATIONS`) | Migrations `001`–`004` (`004_phase14_persistence_and_dr`) | Live SQLite WAL `/app/data/caninesense.sqlite3` (`database_backend: sqlite`, `durable_across_redeploy: false`) | **ARCHITECTURE PASS / PROD EPHEMERAL** |

---

## 2. Phase 13 -> Phase 14 Commit Reconciliation Explanation

Why reported Phase 13 hashes differed across targets (verified intentional, zero drift defects):
1. `588324dc1f85335590e895d1448fdea7248fa31c`: Phase 13 backend + frontend + scripts deployed to Render (`dep-dbuq6ug8v5cc739s64ig`).
2. `cce101d73cce52cbecac71155c8ffed2f169bfce`: Added missing `Danger Zone` account deletion UI in `frontend/src/pages/Settings.tsx` (`DELETE /api/account` already existed in `588324dc`), rebuilt `index-D49uE4oN.js`, and pushed to `gh-pages` (`3c866a9954504c07e600ae560d8c585062a218d5`).
3. `5dd48eb6c51da066c9e841e9c7c36e32f3abeb43`: Committed the 10 Phase 13 `docs/` markdown/JSON reports cleanly (`checkpoint-phase14-20261118`).
4. `44984caa44720212c3ab064eca0885b8a94193c7`: Phase 14 persistence abstraction, DR retention/ZipSlip/health telemetry, JWT revocation on delete, and Phase 14 test/PowerShell automation — deployed live to Render (`dep-dbus42jm8hqs73b8jj7g`) and verified compatible with live GitHub Pages bundle `index-D49uE4oN.js`.

---

## 3. Live Multi-Viewport Acceptance Evidence (`1280x800`, `768x1024`, `390x844`)

Executed autonomously against `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/` (`c3695129-b696-46d2-91c3-02b2109438fb`, host-verified origin `https://sanjaykiran645-beep.github.io`, `blocked_origins: none`):
- **Desktop `1280x800`:** Registration (2 accounts), Dogs provenance, Engine A upload (`1_Stranger_Alert_High_Bark_410Hz.wav` -> `BARK`, `410 Hz` PCM), Engine B synthesis (`blob:` playback), Validation Lab Preregistration + Trial `aebae459` + Invite + JSON/CSV exports, Blind Reviewer Queue acceptance + blind isolation + review submission, Revocation, Theme switching (4 themes), Settings `Danger Zone` deletion + rejected re-login on both synthetic accounts. Zero console/page errors.
- **Tablet `768x1024` & Mobile `390x844`:** Verified Dashboard, Dogs, Analyze, Communicate, Validation Lab, and Settings all rendered non-blank, auto-closed drawer cleanly, and produced zero horizontal overflow (`scrollWidth <= innerWidth`).

**Rollback:** `render deploys create srv-dbq9o9m7bikc73dctmq0 --commit 588324dc1f85335590e895d1448fdea7248fa31c --wait --confirm` and `git checkout checkpoint-phase14-20261118`.
