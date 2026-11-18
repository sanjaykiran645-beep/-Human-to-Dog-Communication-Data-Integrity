# CanineSense AI — Owner Approvals & Actions Required

**Timestamp (UTC):** 2026-11-18T15:35:00Z  
**Commit:** `44984caa44720212c3ab064eca0885b8a94193c7`

Per Rules 13 and 14, no paid upgrades, toolchain installations, or live animal experiments were executed autonomously. The following explicit owner approvals are required to move CanineSense AI from **PARTIAL** to full **PRODUCTION + SCIENTIFIC PASS**:

---

## 1. Financial / Infrastructure Approval (Closes Production Persistence Blocker)

- **Why Required:** Render `plan: free` uses an ephemeral container filesystem; SQLite rows and uploaded audio do not survive redeploy/restart (`durable_across_redeploy: false`).
- **Approve One Option:**
  - **Option A (Minimal Immediate Persistence):** Render Starter Web (`\$7/mo` recurring) + 10 GB Render Persistent Disk (`~\$2.50/mo` recurring, total **~\$9.50/mo**), mounting `/app/data` with `CANINESENSE_PERSISTENT_DISK=1`.
  - **Option B (Multi-Worker Scalable Persistence):** Render Starter Web (`\$7/mo`) + Managed Postgres (`\$7/mo`, total **~\$14/mo recurring**) using Phase 14's `DATABASE_URL` support + Cloudflare R2 / AWS S3 bucket (`\$0` within free quota) wired into `StorageBackend`.
- **Follow-up Check After Approval:** Re-run Phase 14 live persistence acceptance test across a real Render redeploy to prove `durable_across_redeploy: true` and SHA-256 preservation.

---

## 2. Workstation / CI Approval (Closes Android APK Blocker)

- **Why Required:** Rebuilding `mobile-android` into a signed v1.4+ APK requires installing **OpenJDK 17+**, **Android SDK 34**, Gradle wrapper, and `@capacitor/android` (~4.5 GB download/disk usage; `C:` has `18.34 GB` free, `E:` has `132.98 GB` free).
- **Approve:** Either local installation of JDK 17+ & Android SDK 34, or GitHub Actions Android build workflow, plus secure release keystore provisioning outside Git.

---

## 3. Human Scientific & Welfare Oversight (Closes Scientific Validation)

- **Engine A:** Authorize independent canine vocalization dataset collection (`>= 15–20` additional unique dogs per minority class: `growl`, `whine`, `yip`) before retraining.
- **Engine B:** Approve welfare/ethics review and execute owner-consented live canine behavioral trials using preregistered C1–C3 Latin-square protocols and dual blind video reviews.
