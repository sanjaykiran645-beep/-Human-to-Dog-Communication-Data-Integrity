# CanineSense AI — Phase 13 Remaining Blockers

**Assessment Date (UTC):** 2026-11-18T14:46:00Z

---

## 1. Infrastructure & Platform Blockers

1. **Render Free-Tier Ephemeral Disk (`FAIL / BLOCKED without owner budget approval`)**
   - `render.yaml` deploys on `plan: free`, which destroys SQLite (`caninesense.sqlite3`) and uploaded audio files on container restart or redeploy.
   - `/api/health` honestly discloses `persistence.durable_across_redeploy: false`.
   - **Unblock:** Owner approval to provision either a paid Render Starter service + Persistent Disk (`mountPath: /app/data`) or managed PostgreSQL + S3-compatible object storage.

---

## 2. Mobile Release Blockers

2. **Android APK Rebuild Blocked (`BLOCKED`)**
   - `CanineSense_AI_v1.0.0.apk` (`2026-11-07`) is obsolete relative to Priority 7, Priority 8, and Phase 13 (`cce101d7`).
   - Host lacks JDK 17+ (`javac`), Android SDK 34, `gradlew.bat` / `settings.gradle` / root `build.gradle`, and `@capacitor/android` / `@capacitor/cli` in `frontend/package.json`.
   - **Unblock:** Install JDK 17+ and Android SDK 34, initialize Capacitor Android wrapper, configure release signing, and rebuild.

---

## 3. Scientific Validation Blockers (Unresolved — Cannot Be Solved by Code Alone)

3. **Engine A 90% Dog-Independent Target Unmet (`FAIL` — 85.46% vs 90.00%, shortfall 4.54 pp)**
   - Held-out evaluation: 26 dogs / 91 files (`85.46%` balanced accuracy, `86.81%` overall, `78.77%` macro F1, `0.1440` ECE).
   - Training split has only 78 samples across 45 dogs (`1 growl`, `3 whine`, `3 yip`, `46 unknown`); Phase 13 GroupKFold hybrid supervised blending degraded held-out performance (`0.6795`–`0.8515`).
   - **Unblock:** Collect and blindly annotate >= 15–20 additional independent dogs per underrepresented vocalization class (`growl`, `whine`, `yip`) before retraining.

4. **Engine B Biological Efficacy Unvalidated (`NOT VALIDATED` — 0 live canine trials)**
   - DSP synthesis, welfare cap (`75.0 dBA SPL`), Latin-square C1–C3 controls, preregistration, and blind reviewer governance are software-complete.
   - **Unblock:** Conduct owner-consented live canine behavioral trials using preregistered protocols and dual blind video reviews.

5. **Breed & Sex Scaling (`HEURISTIC`)**
   - Allometric mass scaling and male/female F0 priors (`-9%` / `+8%`) lack clinical canine bioacoustic validation; kept explicitly labeled as heuristic context across the UI.
