# CanineSense AI — Red-Team Security Audit

**Date:** 2026-11-18  
**Audited Commit:** `a53e5c13335376be20eb60903bf71904dd8c94ac`  
**Security Pytest Suite:** **13 / 13 PASSED** (`test_auth.py`, `test_security_hardening.py`, `test_security_idor.py`) + `test_client_redteam_audit.py` & `test_experimental_validation.py` included in 143/143 full suite.

---

## 1. Security Controls Verified

| Control Domain | Implementation & Verification | Status |
|---|---|---|
| **Password Hashing** | `bcrypt` with 12-round salt (`backend/app/security.py`); dummy hash timing equalization on login | **PASS** |
| **JWT Signing & Expiry** | HS256 JWT (`PyJWT`), dynamic `CANINESENSE_SECRET_KEY` (or `data/.secret` 0o600 fallback), expiry enforced, `alg: none` and tampered payloads rejected with 401 | **PASS** |
| **Token Revocation** | In-memory `TOKEN_DENYLIST` on `/api/auth/logout` (bounded at 5,000 entries); note denylist is per-process in-memory (`--workers 1` in Dockerfile) | **PASS** |
| **IDOR & Tenant Isolation** | `X-User-Id` header explicitly ignored (`deps.py`); ownership verified on dogs, recordings, media streams, generated audio, participants, cues, and schedules (404 on cross-tenant access) | **PASS** |
| **Upload & MIME Validation** | Magic-byte container sniffing (`audio.py`), 50 MB / 300s bounds, UUID-sanitized storage paths (`storage.py`), fuzzing tests reject PE/ELF/polyglot/truncated files with 400/422 | **PASS** |
| **CORS & Security Headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: same-origin`, `Content-Security-Policy: frame-ancestors 'self'`, `Cache-Control: no-store` on API/media | **PASS** |
| **Rate Limiting & Proxy Spoofing** | Sliding-window in-memory rate limits (`auth`: 40/min, `analyze`: 40/min, `generate`: 50/min, `general`: 240/min); `X-Forwarded-For` ignored unless `CANINESENSE_TRUST_PROXY=1` | **PASS** |
| **Account Erasure** | `DELETE /api/account` erases user, dogs, recordings, analyses, generated audio, private reference uploads, audit events, and (fixed in this audit) Priority 7 experimental tables | **PASS** |
| **Secrets & Git Hygiene** | `.env`, `.secret`, `*.sqlite3`, `logs/` excluded by `.gitignore` and `.dockerignore`; secret grep scan across `backend/app` and `frontend/src` returned 0 hardcoded keys | **PASS** |

---

## 2. Security Findings & Remediations

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| **SEC-01** | MEDIUM | `POST /api/experiments/trials/{trial_id}/reviews` previously returned `primary_observer_category` to any authenticated user knowing a trial UUID. | **PARTIALLY FIXED / OPEN:** Blind reviews (`is_blind_to_condition=True`) no longer return `primary_observer_category`. However, reviewer access still relies on trial UUID secrecy rather than an explicit reviewer-invitation table. |
| **SEC-02** | MEDIUM | `POST /api/experiments/participants` (`dog_id`) and `POST /api/experiments/trials` (`cue_id`, `schedule_id`) did not verify ownership of referenced foreign keys. | **FIXED:** Added strict `user_id == user.id` ownership checks (returns 404 on cross-tenant IDs), verified by `test_schedule_without_seed_and_cross_tenant_fk_isolation`. |
| **SEC-03** | MEDIUM | `mobile-android/android/app/src/main/AndroidManifest.xml` had `android:usesCleartextTraffic="true"`. | **FIXED in source:** Updated to `"false"`. Existing Nov 7 APK remains obsolete until rebuilt. |
| **SEC-04** | LOW | `backend/app/routers/analytics.py` `delete_account` omitted explicit deletion of Priority 7 tables. | **FIXED:** Added explicit deletions for `TrialIndependentReview`, `BehaviouralTrial`, `TrialSchedule`, `ExperimentalCue`, and `StudyParticipant`; verified by `test_account_delete_erases_priority7_experimental_records`. |
| **SEC-05** | INFO | `TOKEN_DENYLIST` and rate-limit buckets are in-memory (`--workers 1` in Dockerfile). | **ACCEPTED FOR SINGLE-WORKER FREE TIER:** Must move to Redis/DB if scaled to multiple Uvicorn workers. |
