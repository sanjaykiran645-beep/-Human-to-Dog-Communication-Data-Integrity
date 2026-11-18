# CanineSense AI — Security Hardening Report (Phase 13)

**Verification Date (UTC):** 2026-11-18T12:53:03Z (Security Hardening suite) & 2026-11-18T14:45:25Z (Live UI QA)  
**Source Script:** `scripts/CanineSense-SecurityHardening.ps1`  
**Log Artifact:** `logs/phase13-security-hardening.json`

---

## 1. Security Remediation Summary

### Blocker Resolved: Trial-UUID Blind Reviewer Access Control
Previously, blind video review relied on possessing a trial UUID without an explicit reviewer-invitation relationship. Phase 13 replaced this pattern with full invitation-backed authorization:
- **`TrialReviewerInvitation` Model (`backend/app/models.py`):** Tracks `trial_id`, `study_owner_user_id`, `invited_by_user_id`, `reviewer_user_id`, `status` (`pending`, `accepted`, `rejected`, `revoked`), `is_blind`, `expires_at`, and response/revocation timestamps.
- **Endpoints Added/Hardened (`backend/app/routers/experiments.py`):**
  - `POST /api/experiments/trials/{trial_id}/invitations` (owner creates invitation for an existing registered user; prevents owner self-invitation).
  - `GET /api/experiments/invitations` (lists incoming and outgoing invitations for the caller).
  - `POST /api/experiments/invitations/{invitation_id}/respond` (`accept` / `reject`; validates expiration and recipient identity).
  - `POST /api/experiments/invitations/{invitation_id}/revoke` (owner revokes access immediately).
  - `GET /api/experiments/assigned-trials` (returns only accepted, non-expired, non-revoked assignments; strips `condition`, protocol assignment, and primary outcome fields whenever `is_blind=True`).
  - `GET /api/experiments/trials/{trial_id}/reviews` restricted to study owner; `POST /api/experiments/trials/{trial_id}/reviews` rejects uninvited users, `pending`/`rejected`/`revoked` invitations, expired invitations, and owner self-review.

### Android & Privacy UI Hardening
- **Cleartext Traffic Disabled:** Added `mobile-android/android/app/src/main/res/xml/network_security_config.xml` (`cleartextTrafficPermitted="false"`) and wired `android:networkSecurityConfig="@xml/network_security_config"` and `android:usesCleartextTraffic="false"` in `AndroidManifest.xml`.
- **Self-Service Account Deletion UI Restored (`frontend/src/pages/Settings.tsx`):** Added `Danger Zone` -> `Delete Account & All Data` card with explicit confirmation checkbox wired to `DELETE /api/account`, aligning `#/app/settings` with the documentation at `#/data-deletion`.

---

## 2. Automated & Live Verification Results

| Check | Status | Details |
|---|---|---|
| Security + Validation pytest suite (`CanineSense-SecurityHardening.ps1`) | **PASS** | `31 passed, 0 failed` (`test_security_hardening.py` + `test_experimental_validation.py` + `test_security_idor.py`). |
| Security regression suite (`CanineSense-Regression.ps1`) | **PASS** | `13 passed, 0 failed` in `backend_security_suite`. |
| Hardcoded secret scan | **PASS** | `0` hardcoded secrets found in scanned tracked source (`hardcoded_secret_hits: 0`). `.env` and `.sqlite3` remain excluded via `.gitignore`. |
| Android cleartext configuration check | **PASS** | `android_cleartext_disabled: true`. |
| Live two-account blind review & revocation QA | **PASS** | Verified in live browser on GitHub Pages + Render: Owner invited Reviewer -> Reviewer accepted -> Assigned trial hid condition & primary outcome -> Reviewer submitted blind review -> Owner revoked invitation -> Both synthetic QA accounts deleted via Settings Danger Zone UI and subsequent login attempts rejected. |
