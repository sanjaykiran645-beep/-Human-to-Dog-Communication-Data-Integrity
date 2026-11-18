# CanineSense AI — Data Durability & Integrity Report (Phase 13)

**Verification Date (UTC):** 2026-11-18T12:51:40Z (pipeline) & 2026-11-18T14:39:35Z (full regression after final UI edit)  
**Source Script:** `scripts/CanineSense-DataIntegrity.ps1`  
**Log Artifact:** `logs/phase13-data-integrity.json`

---

## 1. Architecture & Durability Controls Added

| Control | Implementation File(s) | Behavior |
|---|---|---|
| Schema migration tracking | `backend/app/models.py`, `backend/app/db.py` | `SchemaMigration` table + `apply_migrations()` ledger tracking `001_initial_schema`, `002_priority7_experimental_tables`, `003_phase13_durability_and_governance`. |
| SQLite safety pragmas | `backend/app/db.py` | `PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=WAL`. |
| Storage configuration & health honesty | `backend/app/config.py`, `backend/app/main.py` | Added `STORAGE_PROVIDER`, `USER_STORAGE_QUOTA_BYTES`, `IS_EPHEMERAL_STORAGE`; `/api/health` returns `persistence.durable_across_redeploy`. |
| Atomic I/O & quotas | `backend/app/services/storage.py`, `backend/app/routers/recordings.py` | `atomic_write_bytes`, `user_storage_bytes`, `enforce_user_quota`, raising `StorageQuotaExceededError` (`HTTP 507`) and `StorageUnavailableError` (`HTTP 503`); removed silent swallow in `quick_analyze_recording`. |
| Integrity, orphan & restore audits | `backend/app/services/durability.py` | `verify_database_integrity` (`PRAGMA quick_check` + `foreign_key_check`), `audit_storage_integrity` (verifying `Recording` files, SHA-256 checksums, `GeneratedAudio` + derived `_wave.png`/`_spec.png` plots, and orphan scanning), `create_verified_backup`, `validate_restore_in_isolation`. |
| Cascade account deletion | `backend/app/routers/analytics.py`, `frontend/src/pages/Settings.tsx` | `DELETE /api/account` erases `TrialReviewerInvitation`, `TrialAdverseEvent`, `TrialPreregistration`, trials, recordings, generated audio, dogs, audit events, user storage tree, and private references; Settings UI exposes `Danger Zone` -> `Delete Account & All Data`. |

---

## 2. Verification Results

| Check | Status | Observed Output |
|---|---|---|
| `pytest` durability suite (`backend/tests/test_data_durability.py`) | **PASS** | `3 passed, 0 failed` (standalone & inside 147-test full regression). Tests cover backup/restore SHA-256 + orphan/tamper/missing-file detection, SQLite restart persistence across fresh engines, HTTP 507 quota exceeded, and HTTP 503 storage unavailable. |
| Local DB integrity probe | **PASS** | `integrity_check: ["ok"]`, `foreign_key_violations: 0`, migrations `001`, `002`, `003` present. |
| Local storage integrity probe | **PASS** | `missing_files_count: 0`, `sha256_mismatches_count: 0`, `orphaned_files_count: 0`. |
| Backup & isolated restore probe | **PASS** | Zip backup created (`file_count: 1`) and restored to isolated temp directory (`files_verified: 1`, `checksum_errors: []`, DB integrity `PASS`). |
| Bug discovered & fixed during full suite | **FIXED** | Full regression initially failed with 60 false-positive orphaned files (`test_communicate` + `test_communicator_audio_matrix` derived `_wave.png` / `_spec.png` plots). Updated `durability.py` to register `notes_json` plot paths and `{id}_wave.png`/`{id}_spec.png` sibling cache plots; full 147-test suite subsequently passed `147/147`. |

---

## 3. Production Persistence Gap (Unresolved Free-Tier Limitation)

- Live `GET https://caninesense-backend.onrender.com/api/health` truthfully reports:
  ```json
  "persistence": {
    "provider": "local",
    "durable_across_redeploy": false,
    "note": "Ephemeral container storage active; user data does not survive container replacement until persistent disk or external object storage is configured."
  }
  ```
- **Action required for production durability:** Owner approval to either upgrade Render (`plan: starter` or higher + persistent disk mount at `/app/data`) or provision external S3-compatible object storage + managed PostgreSQL (`DATABASE_URL`).
