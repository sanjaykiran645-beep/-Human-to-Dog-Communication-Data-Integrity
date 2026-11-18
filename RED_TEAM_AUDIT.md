# CanineSense AI — Automated Red-Team Audit

- **Generated UTC:** 2026-11-18T06:39:43Z
- **Repo Root:** `E:\CanineSense_AI_Complete_Project (1)\CanineSense_AI`
- **Git HEAD:** `61f614a1d88ad23bf6b5d5dc80afe65ae5e392af` (branch ref: `ref: refs/heads/main`)
- **GitHub Pages Ref:** `d18162458183f76138b8fd329bd66e3d215158b5`
- **APK SHA-256:** `E17BD6DD6221DDB2A78E99817355BCA409F2F6945910F4BEC854585686AA34AC`
- **Total Files Audited (excluding build/git/cache):** 630

## Classification Totals

| Classification | Count |
|---|---:|
| SECURITY RISK | 1 |
| OBSOLETE | 1 |
| REQUIRES OWNER INPUT | 2 |
| PASS | 608 |
| MISSING | 0 |
| UNUSED | 0 |
| DUPLICATE | 17 |
| DEFECTIVE | 1 |

## Verified Findings

| ID | Severity | Category | File | Status | Summary |
|---|---|---|---|---|---|
| RT-INFRA-01 | MEDIUM | CI/CD | `.github/workflows` | MISSING | No .github/workflows directory exists; GitHub Pages/CI deployment is manual or external. |
| RT-SEC-01 | MEDIUM | Authorization/Privacy | `backend/app/routers/experiments.py` | SECURITY RISK | submit_independent_review hides primary_observer_category during blind reviews, but relies on trial UUID secrecy rather than an explicit reviewer invite/assignment table. |
| RT-DEP-01 | HIGH | Persistence | `render.yaml` | DEFECTIVE | Render free tier without persistent disk makes SQLite (/app/data/caninesense.sqlite3) and /app/data/storage ephemeral across deploys/restarts. |
| RT-MOB-02 | HIGH | ReleaseConsistency | `CanineSense_AI_v1.0.0.apk` | OBSOLETE | Packaged APK (122203 bytes, LastWrite=2026-11-11 14:19:02Z, SHA256=E17BD6DD6221DDB2A78E99817355BCA409F2F6945910F4BEC854585686AA34AC) contains Nov 7 minimal assets (index-B_fOKfw7.js) and stub dex, diverging from Priority 7/8 web source. |
| RT-DUP-01 | LOW | DuplicateAsset | `data/releases/CanineSense_AI_v1.0.0.apk` | DUPLICATE | Identical binary copy of root CanineSense_AI_v1.0.0.apk. |
| RT-DUP-02 | LOW | Documentation | `docs/*` | DUPLICATE | 16 report/spec files exist in both repo root and docs/ (1 diverges: engine_b_action_taxonomy.md). |
