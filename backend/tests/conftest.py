"""Test fixtures. Isolated data directory and secret."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

TMP = Path(tempfile.mkdtemp(prefix="caninesense-test-"))
os.environ["CANINESENSE_SECRET_KEY"] = "test-secret-key-not-for-production-use-32b"
os.environ["CANINESENSE_DATA_DIR"] = str(TMP)
os.environ["CANINESENSE_ENV"] = "test"

# Isolate the Engine B reference library: tests work on a copy, never the real manifest/audio.
import shutil  # noqa: E402

_REAL_REF = Path(__file__).resolve().parents[2] / "data" / "reference_library"
_TEST_REF = TMP / "reference_library"
if _REAL_REF.exists():
    shutil.copytree(_REAL_REF, _TEST_REF, ignore=shutil.ignore_patterns("*.bak*", "*.tmp"))
os.environ["CANINESENSE_REFERENCE_DIR"] = str(_TEST_REF)

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    init_db()
    return TestClient(app)


@pytest.fixture
def user_a(client: TestClient) -> dict:
    email = f"a-{os.urandom(4).hex()}@example.com"
    res = client.post("/api/auth/register", json={"email": email, "password": "correcthorse", "name": "Ada"})
    assert res.status_code == 200, res.text
    data = res.json()
    return {"token": data["access_token"], "user": data["user"], "email": email}


@pytest.fixture
def user_b(client: TestClient) -> dict:
    email = f"b-{os.urandom(4).hex()}@example.com"
    res = client.post("/api/auth/register", json={"email": email, "password": "correcthorse", "name": "Bea"})
    assert res.status_code == 200, res.text
    data = res.json()
    return {"token": data["access_token"], "user": data["user"], "email": email}


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def write_tone(path: Path, freq: float, seconds: float, sr: int = 22050, noise: float = 0.0) -> Path:
    t = np.arange(int(sr * seconds)) / sr
    y = 0.2 * np.sin(2 * np.pi * freq * t)
    if noise:
        y = y + noise * np.random.default_rng(0).normal(0, 1, y.shape)
    peak = np.max(np.abs(y)) + 1e-9
    sf.write(str(path), (y / peak * 0.8).astype(np.float32), sr)
    return path


def write_bursts(path: Path, sr: int = 22050, n: int = 4) -> Path:
    pieces = []
    rng = np.random.default_rng(1)
    for _ in range(n):
        dur = 0.16
        t = np.arange(int(sr * dur)) / sr
        burst = rng.normal(0, 1, t.shape)
        env = np.exp(-t * 18)
        pieces.append(burst * env * 0.5)
        pieces.append(np.zeros(int(0.18 * sr)))
    y = np.concatenate(pieces)
    sf.write(str(path), y.astype(np.float32), sr)
    return path
