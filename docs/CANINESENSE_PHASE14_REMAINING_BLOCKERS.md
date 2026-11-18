# CanineSense AI — Phase 14 Remaining Blockers

**Timestamp (UTC):** 2026-11-18T15:35:00Z  
**Commit:** `44984caa44720212c3ab064eca0885b8a94193c7`  
**Rollback Tag:** `checkpoint-phase14-20261118`

| # | Blocker | Severity | Status | Evidence / Cause | Unblock Action |
|---|---|---|---|---|---|
| 1 | Production database & audio file persistence across Render redeploys | **CRITICAL (Production)** | **BLOCKED — OWNER INFRASTRUCTURE APPROVAL REQUIRED** | `render.yaml` uses `plan: free` ephemeral disk (`durable_across_redeploy: false`, `backup_status: WARN_NO_BACKUPS`). | Owner approval for Render Persistent Disk (~\$9.50/mo) or Managed Postgres + R2/S3 (~\$14/mo), then verify across real redeploy. |
| 2 | Obsolete Android APK (`CanineSense_AI_v1.0.0.apk`, 2026-11-07) | **HIGH (Mobile)** | **BLOCKED** | Missing JDK 17+ (`javac`), Android SDK 34, Gradle wrapper, `@capacitor/android` / `@capacitor/cli`. | Install toolchain (~4.5 GB) or build via Android CI, then run `npm run build && npx cap sync android && ./gradlew assembleRelease`. |
| 3 | Engine A 90% dog-independent balanced accuracy target | **SCIENTIFIC** | **FAIL (85.46% vs 90.00%, -4.54 pp)** | 26 test dogs / 91 files; training split limited to 78 files across 45 dogs (`1 growl`, `3 whine`, `3 yip`). | Collect >= 15–20 new unique dogs per minority class with independent expert annotation. |
| 4 | Engine B live behavioral validation | **SCIENTIFIC** | **NOT VALIDATED** | `0` live canine trials; `0.0%` empirically verified congruence; comprehension unestablished. | Conduct preregistered C1–C3 live canine trials with independent blind reviewers. |
| 5 | Breed/sex acoustic scaling clinical validity | **SCIENTIFIC** | **HEURISTIC** | Allometric & sex multipliers (`-9%` / `+8%`) are unvalidated literature heuristics. | Explicitly keep heuristic labeling in UI until empirical canine acoustic study validates priors. |
