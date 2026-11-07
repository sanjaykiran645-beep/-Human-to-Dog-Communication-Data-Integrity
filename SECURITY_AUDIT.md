# Security audit

Verified by tests (`test_security_idor.py`, `test_generated_audio_idor`):

- Unauthenticated `/api/dogs` → 401
- User B cannot GET User A dog, recording, media, or generated WAV (404)
- `X-User-Id` header ignored

Controls retained:

- bcrypt passwords, JWT from server secret
- Owner-scoped queries
- Private storage paths, authorized media
- CORS `allow_credentials=False` with `allow_origins=["*"]` (Bearer tokens, not cookies)
- Upload size/type validation; no shell interpolation of filenames
- 500 responses do not include stack traces

Remaining: no dedicated XSS/CSRF browser suite; SQLite has no RLS (enforced in application code).
