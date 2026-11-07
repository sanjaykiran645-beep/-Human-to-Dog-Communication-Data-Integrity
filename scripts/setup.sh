#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — set CANINESENSE_SECRET_KEY before production."
fi
python3 -m pip install -r backend/requirements.txt
python3 scripts/init_db.py
(cd frontend && npm install)
echo "Setup complete."
