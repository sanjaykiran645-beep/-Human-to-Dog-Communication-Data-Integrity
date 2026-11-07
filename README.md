# CanineSense AI

Private website for dog vocalization analysis (**Engine A**) and experimental human→dog sound generation (**Engine B**).

A bark is an acoustic event. This product does **not** translate a dog’s mind, and it does **not** claim that a generated sound will be understood.

The 90% independent-accuracy target is an evaluation goal. **It is not met** in this build: no dog-held-out annotated corpus of sufficient size is bundled.

## 1. Project overview

CanineSense is a single-user-account web application:

- Public landing page, registration, and login
- Authenticated lab: dashboard, analyze, communicate, dog profiles, history, analytics, settings
- Server-side audio inference (not a fake frontend classifier)
- Per-account private storage of recordings and results

## 2. System architecture

```
Browser (React + Vite)
    /api  proxy
FastAPI
    ├── Auth (bcrypt + JWT)
    ├── Engine A  audio → features → classify → behavior → explain
    ├── Engine B  intent → DSP synthesis → optional Engine A on response
    ├── SQLite (ownership on every private row)
    └── data/storage/{user_id}/…  (private files, authorized download only)
```

## 3. Prerequisites

- Python 3.11 or newer (3.13 is fine)
- Node.js 20 or newer and npm
- ffmpeg on PATH (audio decode)
- pip

**Windows (PowerShell, run as needed):**

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
```

Confirm:

```powershell
python --version
node --version
ffmpeg -version
```

**macOS / Linux:** install Python, Node, and `ffmpeg` from your package manager.

## 4. Installation

Unzip the archive, then from the project root:

**PowerShell**

```powershell
cd path\to\CanineSense_AI
.\scripts\setup.ps1
```

**bash**

```bash
cd path/to/CanineSense_AI
chmod +x scripts/setup.sh
./scripts/setup.sh
```

Manual equivalent:

```powershell
python -m pip install -r backend/requirements.txt
cd frontend
npm install
cd ..
```

## 5. Environment configuration

Copy the example file. Never commit a real `.env`.

```powershell
Copy-Item .env.example .env
```

| Variable | Purpose |
|---|---|
| `CANINESENSE_SECRET_KEY` | JWT signing key. Replace the placeholder in production with a long random string. |
| `CANINESENSE_ENV` | `development` or `production` |
| `CANINESENSE_DATA_DIR` | Data root (default `./data`) |
| `CANINESENSE_ACCESS_TOKEN_MINUTES` | Token lifetime (default 1440) |

If `CANINESENSE_SECRET_KEY` is unset, the server writes a random key to `data/.secret` (not for production sharing).

## 6. Database setup

SQLite is created automatically on first API start. To create tables explicitly:

```powershell
python scripts/init_db.py
```

Schema lives in SQLAlchemy models (`backend/app/models.py`). `docs/SCHEMA.sql` is documentation only. There is no hosted Postgres/Supabase in this distribution.

## 7. Backend startup

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/api/health  
OpenAPI: http://127.0.0.1:8000/api/docs

## 8. Frontend startup

In a second terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Or both windows at once:

```powershell
.\scripts\dev.ps1
```

## 9. How to access the website

Open **http://127.0.0.1:5173/**

- `/` landing
- `/register` create account
- `/login` sign in
- `/app` authenticated lab

The browser talks to `/api/...` on the same origin. Vite proxies those calls to port 8000. Do not point the browser at `localhost:8000` from a remote preview.

## 10. Engine A (dog → human)

1. Sign in → **Dog profiles** (optional) → **Analyze**
2. Upload WAV/MP3/M4A/OGG/WEBM (max 15 MB, 60 s) or use **Rec**
3. Wait for server inference (not a local fake)
4. Read class, confidence, unknown/abstain, spectrogram, evidence, limitations
5. Results persist under **History**

## 11. Engine B (human → dog)

1. **Communicate** (experimental)
2. Type a cue (`come here`, `stay`, `good dog`, `easy`) or use on-device speech
3. If the intent is ambiguous, pick a category
4. Play the **synthetic** sound
5. Optionally record a 5 s dog response — Engine A scores it independently
6. A response is **not** proof the dog understood the sound

## 12. Tests

From the project root:

```powershell
python -m pytest -q
```

Covers auth, cross-user isolation (IDOR), invalid audio, abstention, synthesis, and generation.

## 13. Production build

```powershell
cd frontend
npm run build
cd ..
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

When `frontend/dist` exists, FastAPI also serves the website (SPA fallback). For a static preview with API proxy:

```powershell
cd frontend
npm run preview -- --host 127.0.0.1 --port 4173
```

Set a real `CANINESENSE_SECRET_KEY` before any shared deployment.

## 14. Security configuration

- Identity comes only from the JWT, never from `X-User-Id`
- Every query is scoped to `user_id == token.sub`
- Audio is not publicly listed; media routes require the owner’s token
- No service-role keys, cloud keys, or passwords belong in the frontend
- `.env` and `data/` are gitignored and excluded from the source ZIP
- Recordings are not sent to third-party AI APIs

## Troubleshooting: “Audio decoder is not available on the server”

FFmpeg is required for WEBM/Opus (typical browser MediaRecorder), MP3, M4A, and OGG. WAV/FLAC work without it.

**Windows PowerShell**

```powershell
winget install Gyan.FFmpeg
ffmpeg -version
# If still not found:
# $env:FFMPEG_PATH = "C:\ffmpeg\bin\ffmpeg.exe"
```

**Debian/Ubuntu**

```bash
sudo apt-get install -y ffmpeg
ffmpeg -version
```

This project’s Analyze screen also records PCM WAV in the browser so microphone analysis can succeed even when WEBM decode is unavailable. Check `GET /api/health` → `decoder`.

## 15. Known limitations

- 90% independent accuracy is **not achieved** (no labeled held-out dog corpus)
- Behavioral valence is undetermined from audio alone
- Engine B is experimental DSP, not a learned vocoder
- Intent matching is keyword-based
- SQLite is single-node; not a multi-region production database
- Browser microphone and Web Speech require user permission and a capable browser

See `docs/MODEL_CARD.md`, `docs/ANNOTATION_POLICY.md`, `docs/API.md`, and `DELIVERY_REPORT.md`.
