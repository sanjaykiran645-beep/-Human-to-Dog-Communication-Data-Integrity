# CanineSense AI — Phase 13 Deployment Traceability

**Traceability Audit (UTC):** 2026-11-18T14:46:00Z  
**Repository:** https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity

---

## 1. Environment-to-Commit Traceability Matrix

| Target / Artifact | Live Version / Identifier | Deployed / Verified At (UTC) | Notes |
|---|---|---|---|
| **Rollback Tag (`main`)** | `checkpoint-phase13-20261118` (`a53e5c13335376be20eb60903bf71904dd8c94ac`) | `2026-11-18` | Pre-Phase-13 clean production baseline preserved. |
| **GitHub `main` (code)** | `cce101d73cce52cbecac71155c8ffed2f169bfce` (includes `588324dc1f85335590e895d1448fdea7248fa31c`) | `2026-11-18T14:41:35Z` | Fast-forward push after regression pass; docs commit follows cleanly. |
| **Render Backend (`srv-dbq9o9m7bikc73dctmq0`)** | `dep-dbuq6ug8v5cc739s64ig` at commit `588324dc1f85335590e895d1448fdea7248fa31c` | `2026-11-18T13:10:21Z` | `status: live`. `cce101d7` touched only `frontend/src/pages/Settings.tsx`, so Python backend at `588324dc` is byte-identical to `cce101d7`. `58` OpenAPI routes live. |
| **GitHub Pages (`gh-pages`)** | `3c866a9954504c07e600ae560d8c585062a218d5` (built from `cce101d73cce52cbecac71155c8ffed2f169bfce`) | `2026-11-18T14:41:43Z` | Serves `index-D49uE4oN.js` (`481.34 kB`) and `index-u4mLwK6I.css`. Verified `HTTP 200` + live browser QA PASS. |
| **Android APK (`CanineSense_AI_v1.0.0.apk`)** | Built `2026-11-07`, SHA-256 `E17BD6DD6221DDB2A78E99817355BCA409F2F6945910F4BEC854585686AA34AC` | Obsolete (`2026-11-07`) | **Not rebuilt (`BLOCKED`)** due to missing JDK 17+, Android SDK 34, Gradle, and `@capacitor/android`. |
