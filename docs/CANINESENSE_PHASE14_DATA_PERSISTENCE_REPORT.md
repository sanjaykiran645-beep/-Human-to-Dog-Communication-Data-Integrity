# CanineSense AI — Phase 14 Data Persistence & Storage Architecture Report

**Timestamp (UTC):** 2026-11-18T15:35:00Z  
**Commit:** `44984caa44720212c3ab064eca0885b8a94193c7`  
**Scripts Executed:** `CanineSense-Phase14-Persistence.ps1`, `CanineSense-DataIntegrity.ps1` (`logs/phase14-persistence.json`, `logs/phase13-data-integrity.json`)  
**Architecture Gate Status:** **PASS** (`5/5` durability/DR pytest tests)  
**Production Data Durability Status:** **BLOCKED — OWNER INFRASTRUCTURE APPROVAL REQUIRED**

---

## 1. Complete Data Category Inventory (15 Categories Audited)

| Category | Model / Source | Physical Storage (Current) | Persistence & Backup | Ownership & Deletion | Survives Render Redeploy? |
|---|---|---|---|---|---|
| User accounts | `models.User` (`users`) | `/app/data/caninesense.sqlite3` | SQLite WAL + FK; backup zip snapshot | Self (`user.id`); erased by `DELETE /api/account` + JWT revoked | **NO** (Free tier) |
| Dog profiles | `models.Dog` (`dogs`) | `/app/data/caninesense.sqlite3` | SQLite WAL + FK; backup zip | `dog.user_id`; deleted on account erase | **NO** |
| Uploaded audio | `models.Recording` + files | `/app/data/storage/<uid>/recordings/<rid>/` | Atomic temp write + SHA-256; included in backup zip | User-scoped `resolve_owned`; quota 250 MB; erased via `delete_user_tree` | **NO** |
| Audio analysis & Engine A results | `models.Analysis` (`analyses`) | `/app/data/caninesense.sqlite3` | SQLite WAL + FK; backup zip | `analysis.user_id`; erased on account delete | **NO** |
| Engine B generated audio | `models.GeneratedAudio` + WAV/PNG | `/app/data/storage/<uid>/generated/` | Atomic write + plot tracking in `durability.py` | `gen.user_id`; erased via `delete_user_tree` | **NO** |
| Reference audio metadata (shared & user) | `manifest.csv` + custom files | Bundled image (`/app/data/reference_library`) + user dir | Shared corpus read-only in Docker image; user uploads ephemeral | Shared=`None` (403 on mutate); private=`owner_user_id` + `purge_user_references` | Shared **YES**, User **NO** |
| Behavioural Validation Lab participants | `models.StudyParticipant` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | `participant.user_id`; erased on account delete | **NO** |
| Trial records | `models.BehaviouralTrial` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | `trial.user_id`; erased on account delete | **NO** |
| Reviewer invitations | `models.TrialReviewerInvitation` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | Owner or invited reviewer cleaned on `DELETE /api/account` | **NO** |
| Reviewer submissions | `models.TrialIndependentReview` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | Cleaned for reviewer (`reviewer_user_id`) and owned trials on `DELETE /api/account` | **NO** |
| Research annotations / preregistrations | `models.TrialPreregistration` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | `user_id`; erased on account delete | **NO** |
| Experiment schedules & adverse events | `TrialSchedule`, `TrialAdverseEvent` | `/app/data/caninesense.sqlite3` | SQLite WAL + FK | `user_id`; erased on account delete | **NO** |
| Audit logs & schema migrations | `AuditEvent`, `SchemaMigration` | `/app/data/caninesense.sqlite3` | SQLite WAL; `001`–`004` tracked | `AuditEvent` for `uid` purged on `DELETE /api/account`; `SchemaMigration` system-level | **NO** |
| Signing secrets | `CANINESENSE_SECRET_KEY` env / `.secret` | Render env var (`generateValue: true`) | Managed by Render env config | N/A | **YES** (via Render env var) |

---

## 2. Provider-Independent Improvements Implemented (Phase 14)

- **Database Engine Abstraction (`backend/app/config.py`, `backend/app/db.py`):** Added `CANINESENSE_DATABASE_URL` / `DATABASE_URL` support (`postgres://` normalization), setting `DB_BACKEND` (`"sqlite"` vs `"postgresql"`), skipping SQLite `check_same_thread` and PRAGMAs for PostgreSQL, and registering migration `"004_phase14_persistence_and_dr"`.
- **Storage Contract Expansion (`backend/app/services/storage.py`):** Extended `StorageBackend` / `LocalStorageBackend` with `read_bytes`, `exists`, `delete_rel`, `list_user_keys`, and added `cleanup_stale_temp_files` to remove abandoned `.tmp_*` partial uploads.
- **Health Telemetry (`backend/app/main.py`):** Live `/api/health` now exposes `"database_backend": "sqlite"`, `"durable_across_redeploy": false`, `"backup_status": "WARN_NO_BACKUPS"`, `"backup_count": 0`, without leaking host paths.

---

## 3. Durable Infrastructure Comparison (Owner Decision Required)

| Option | Recurring Cost | Persistence Guarantee | Backup & Restore | Migration Effort | Recommendation |
|---|---|---|---|---|---|
| **Current Render `plan: free`** | \$0/mo | **NONE** (ephemeral disk wiped every restart/deploy) | Local zip lost with container | Current | Unsuitable for user retention |
| **Option A: Render Starter Web + 10 GB Persistent Disk** | **\$7/mo web + ~\$2.50/mo disk (~ \$9.50/mo recurring)** | Single-region Render Persistent Disk mounted at `/app/data` (zero downtime zero-rewrite for SQLite + WAVs) | Render Disk snapshots + `durability.py` zip backups (`CANINESENSE_PERSISTENT_DISK=1`) | Minimal (update `render.yaml`, ~10 min) | **Lowest-cost immediate durability** |
| **Option B: Render Starter Web (\$7/mo) + Managed Postgres (\$7/mo) + Cloudflare R2 / AWS S3 (free tier <=10 GB, egress \$0 on R2)** | **~\$14/mo recurring (+ S3/R2 usage above free quota)** | High-durability ACID Postgres + multi-AZ object storage | Automated managed Postgres PITR + S3 versioning | Medium (wire S3 adapter to `StorageBackend` Protocol; DB ready via `DATABASE_URL`) | **Best long-term multi-worker architecture** |

**Rule 13 Notice:** No paid Render plan upgrade, persistent disk, or paid database/storage subscription was created.

---

## 4. Persistence Acceptance & Test Results

- **Local Persistence Lifecycle + Engine Restart Test (`test_phase14_persistence_acceptance_lifecycle_and_restart`):** **PASS** — Created owner & reviewer accounts, dog (`DrDog`), uploaded `p14_bark.wav` (verified SHA-256), created participant + trial + reviewer invitation, disposed SQLAlchemy engine and opened fresh engine against same DB file, verified SHA-256 and DB rows survived, verified cross-user isolation, and cleaned up both synthetic accounts.
- **Live Render Restart/Redeploy Persistence Test:** **BLOCKED — OWNER INFRASTRUCTURE APPROVAL REQUIRED**. Live `/api/health` confirms `"durable_across_redeploy": false`.

**Rollback:** `git checkout checkpoint-phase14-20261118` or `render deploys create srv-dbq9o9m7bikc73dctmq0 --commit 588324dc1f85335590e895d1448fdea7248fa31c --wait --confirm`.
