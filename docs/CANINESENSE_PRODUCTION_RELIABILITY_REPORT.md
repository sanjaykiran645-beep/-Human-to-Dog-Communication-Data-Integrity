# CanineSense AI — Production Reliability & Live QA Report (Phase 13)

**Verification Date (UTC):** 2026-11-18T14:45:59Z  
**Production Frontend:** https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/  
**Production Backend:** https://caninesense-backend.onrender.com

---

## 1. Automated Verification Post-Final-Edit (`CanineSense-Regression.ps1` & `CanineSense-Release-Verify.ps1`)

| Check Suite | Status | Result | Observed Timestamp (UTC) |
|---|---|---|---|
| `backend_pytest_full` | **PASS** | `147 passed, 0 failed, 0 skipped` (`154.16s`) | `2026-11-18T14:37:49Z` |
| `backend_priority8_audio_matrix` | **PASS** | `23 passed, 0 failed, 0 skipped` (`29.85s`) | `2026-11-18T14:38:19Z` |
| `backend_priority7_validation_lab` | **PASS** | `12 passed, 0 failed, 0 skipped` (`19.11s`) | `2026-11-18T14:38:38Z` |
| `backend_security_suite` | **PASS** | `13 passed, 0 failed, 0 skipped` (`34.93s`) | `2026-11-18T14:39:13Z` |
| `frontend_lint_oxlint` | **PASS** | `0 errors` (`33 warnings`, `35` files, `3.75s`) | `2026-11-18T14:39:17Z` |
| `frontend_typecheck_tsc` | **PASS** | `0 errors` (`13.44s`) | `2026-11-18T14:39:30Z` |
| `frontend_vite_build` | **PASS** | Bundle `index-D49uE4oN.js` (`481.34 kB`), `index-u4mLwK6I.css` (`30.42 kB`), `mockBackend-BL72I4S1.js` (`12.82 kB`) | `2026-11-18T14:39:35Z` |
| `backend_smoke` (local ASGI) | **PASS** | `/api/health = 200`, `58` OpenAPI routes | `2026-11-18T14:45:56Z` |
| `live_backend_health` (Render) | **PASS** | `HTTP 200`, `58` OpenAPI routes, `ffmpeg_available: true`, `persistence.durable_across_redeploy: false` | `2026-11-18T14:45:58Z` |
| `live_frontend_shell` (GitHub Pages) | **PASS** | `HTTP 200` (`1362` bytes), serving `index-D49uE4oN.js` | `2026-11-18T14:45:59Z` |

---

## 2. Live Production Browser Acceptance QA Summary

Verified across two browser QA runs (`fa0a6b30-bd1c-4e38-92aa-192ea7edb525`) against `https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/` (host-verified origin `https://sanjaykiran645-beep.github.io`, `blocked_origins: none`):

1. **Desktop `1280x800` Initial Load & Two-Account Creation:** Passed with zero console/page errors. Registered synthetic `phase13qa2_948271@example.com` and `phase13qa1_948271@example.com`.
2. **Dogs Profile Provenance:** Created `Phase13Dog` (Beagle, Male, `11.5 kg`), verified `Male Dog (Heuristic Prior: -9% F0)`, `Female Dog (Heuristic Prior: +8% F0)`, and Phase 13 provenance notice rendered without overflow.
3. **Engine A Analysis (`1_Stranger_Alert_High_Bark_410Hz.wav`):** Verified `HEURISTIC RULE MATCH: 95%`, `VOCALIZATION: BARK`, `410 Hz (Measured from audio PCM)`, heuristic arousal notice, and breed context prior disclaimer.
4. **Engine B Synthesis & Playback:** Verified `Heuristic prior: Phase13Dog (Beagle · MALE — unvalidated allometric/sex scaling)` label, synthesized `"Come here"`, and confirmed audio `blob:` playback loaded without 4xx/5xx errors.
5. **Validation Lab Governance (2-Account Blind Flow & Exports):**
   - Created Study Preregistration, enrolled dog, recorded Trial #1 (`119b733c`), invited `phase13qa2_948271@example.com`, exported `caninesense_pseudonymous_export.json` and `.csv`.
   - Signed in as Reviewer (`phase13qa2_948271@example.com`), accepted invite, verified Assigned Blind Trials hid condition assignment and primary score, submitted independent blind review.
   - Signed back in as Owner, revoked reviewer invitation cleanly (`status: revoked`).
6. **UI Defect Found, Fixed, & Verified:**
   - First QA run discovered `#/app/settings` lacked the `Danger Zone -> Delete Account & All Data` UI promised by `#/data-deletion`. Added the card in `frontend/src/pages/Settings.tsx` (`cce101d7`), deployed `index-D49uE4oN.js` (`3c866a99`), re-verified zero console/network errors, and permanently deleted both synthetic QA accounts via UI (confirmed subsequent login attempts rejected).
7. **Theme Switching & Mobile `390x844` Responsiveness:** Verified all 4 themes switch cleanly and zero horizontal overflow (`scrollWidth <= innerWidth`, `htmlW: 374.67`) across Dashboard, Dogs, Analyze, Communicate, Validation Lab, and Settings.
8. **Transient Network Observation:** During initial QA (around Step 78), one transient Render proxy fetch/CORS failure banner occurred (Render logs showed 200 OK on all Python requests, consistent with Render free-tier proxy/cold-start behavior). Zero errors occurred on the final re-verification pass.
