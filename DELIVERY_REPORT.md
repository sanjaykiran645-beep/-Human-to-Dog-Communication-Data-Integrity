# CanineSense AI — delivery report

Date: 2026-11-01  
Workspace at audit: **empty**. No prior frontend, backend, models, or datasets existed. Everything below was built from that empty tree.

Production-readiness decision: **NOT production-ready** for any claim of 90% vocalization accuracy, canine emotion translation, or dog comprehension. **Usable** as a private experimental acoustic lab with honest labels.

## 1. Final architecture

Single-process modular monolith.

- React/Vite UI → `/api` proxy → FastAPI
- JWT auth (bcrypt passwords)
- SQLite with `user_id` ownership on every private table
- Private filesystem `data/storage/{user_id}/...`
- Engine A: decode → validate → preprocess → features → classify → behavior → explain → persist
- Engine B: intent (rules) → DSP synthesis → optional Engine A analysis of a recorded response

Model versions are stored on every analysis row.

## 2. Implemented features

| Area | Status |
|---|---|
| Auth register/login/logout/password | PASS |
| Dog profiles CRUD | PASS |
| Upload + microphone recording | PASS (API + UI; browser mic needs user permission) |
| Audio validation & preprocessing | PASS |
| Acoustic feature extraction | PASS |
| Vocalization classification (live inference) | PASS |
| Unknown / abstention | PASS |
| Behavioral context (conservative, separate) | PASS |
| Explainable evidence from measured features | PASS |
| Human intent + experimental DSP generation | PASS |
| Dog-response recording analyzed independently | PASS |
| History, dashboard, analytics, settings, export, delete | PASS |
| Cross-user isolation tests | PASS |
| 90% independent accuracy | BLOCKED |
| Supervised model trained on real dogs | NOT STARTED (pipeline only) |
| Browser end-to-end UI tests | NOT STARTED |
| Full pentest matrix | PARTIAL |

## 3. Working workflows

Dog→human: authenticate → optional dog → upload/record → reject invalid audio → store original + processed WAV → quality → features → classifier → behavior → explanation → history.

Human→dog: authenticate → text or on-device speech → intent → clarification if ambiguous → synthetic WAV clearly marked experimental → optional 5s response → Engine A independently.

Failures do not show success. Analysis is not simulated.

## 4. AI model details

Production: `acoustic-heuristic-v1.0.0`  
Literature-informed membership functions on real librosa/scipy features, softmax probabilities, abstain if max probability or margin is weak, or quality is reject/poor.

Not a deep network. Not trained on a hidden private corpus.

## 5. Dataset

None bundled. Annotation policy and evaluation entry points exist (`docs/ANNOTATION_POLICY.md`, `backend/app/ml/evaluate.py`). Gap: multi-dog, multi-class, human-reviewed recordings with session ids.

## 6. Evaluation methodology

Group split by `dog_id`. Synthetic/augmented rows forbidden in test. Metrics implemented: accuracy, balanced accuracy, macro P/R/F1, per-class, confusion matrix. No numbers are invented.

## 7. Measured accuracy

**Not measured on real dogs.** Target 90% balanced accuracy: **not achieved**. Health and model-card endpoints report `accuracy_target_met: false`.

Unit tests only check that long tonal signals are not called yips and burst sequences are not called howls — pipeline sanity, not accuracy.

## 8. Per-class performance

Unavailable (no labeled held-out set).

## 9. Voice-generation evaluation

DSP outputs are finite, class-distinct in duration (howl ≫ yip), and labeled synthetic. No dog-response experiment was run. Dog comprehension is **not claimed**.

## 10. Security controls

- JWT from server secret (env or `data/.secret`, never in frontend)
- Password hashing with bcrypt
- Ownership checks on every read/write/media route
- Client `X-User-Id` ignored
- Rate limits on auth and general traffic
- Upload size/type/decode validation; no shell interpolation of filenames
- Private storage; media only via auth
- Security headers; no stack traces in 500s
- Account delete removes DB rows and user tree

## 11. Security tests

PASS: unauthenticated access denied; duplicate email rejected; User B cannot read User A dog, recording, or generated audio; spoofed user-id header ignored.

NOT STARTED as dedicated suites: XSS in names, CSRF (Bearer tokens, not cookies), rate-limit bypass, pentest of ffmpeg decoder.

## 12. Database

SQLite tables: users, dogs, recordings, analyses, generated_audio, dog_responses, audit_events. Foreign keys on. Authorization is query-scoped `user_id == token.sub` (SQLite has no RLS).

## 13. API

See `docs/API.md`. OpenAPI at `/api/docs`.

## 14. Tests

`python3 -m pytest -q` — 20 tests covering auth, IDOR, audio rejection, classifier abstention, intent, synthesis, analyze inference, experimental generation.

## 15. Known limitations

- Heuristic acoustic model, not independently validated
- Valence never claimed from audio
- Intent engine is keywords, not NLU
- Synthesis is DSP, not a learned canine vocoder
- Single-node SQLite
- No object-storage signed URLs (local private files instead)

## 16. Incomplete requirements

- 90% target (data gap)
- Probability calibration on real data
- Independent human annotation workflow UI
- Load/performance campaign
- Browser E2E

## 17. Deployment

Run backend `:8000` and frontend `:5173` as in README. Set `CANINESENSE_SECRET_KEY` in production. Do not expose `data/`.

## 18. Decision

Ship as an **experimental private lab**. Do not market as a 90% accurate translator.

## 19. Website completion (this delivery)

Public landing `/`, registration `/register`, login `/login`, authenticated lab `/app/*` with sidebar (mobile menu). Engine A and Engine B call the live FastAPI routes. Production frontend build: **PASS** (`tsc -b && vite build`). Automated tests: **20 passed**. API workflow register → dog → analyze → generate: **PASS**.

ZIP: `CanineSense_AI_Complete_Project.zip` (source only). Excludes `node_modules`, `dist`, `.env`, `data/.secret`, SQLite, recordings. Placeholders only in `.env.example`.
