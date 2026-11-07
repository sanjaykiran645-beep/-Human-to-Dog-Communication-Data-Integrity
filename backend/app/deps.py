"""Auth dependencies. Ownership is always taken from the verified token, never the client."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .config import RATE_LIMIT_ANALYZE, RATE_LIMIT_AUTH, RATE_LIMIT_GENERAL, RATE_LIMIT_GENERATE, RATE_LIMIT_WINDOW_SEC
from .db import get_db
from .security import decode_token

bearer = HTTPBearer(auto_error=False)

_hits: dict[str, deque[float]] = defaultdict(deque)


_TRUST_PROXY = os.getenv("CANINESENSE_TRUST_PROXY", "0").strip() in {"1", "true", "yes"}


def _client_ip(request: Request) -> str:
    # X-Forwarded-For is attacker-controlled unless a trusted reverse proxy sets it; honouring it by
    # default lets a client dodge rate limits by rotating the header.
    if _TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()[:80]
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, bucket: str, limit: int) -> None:
    ip = _client_ip(request)
    key = f"{bucket}:{ip}"
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > RATE_LIMIT_WINDOW_SEC:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please wait.")
    q.append(now)
    if len(_hits) > 5000:  # bound memory: drop idle keys
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > RATE_LIMIT_WINDOW_SEC]:
            _hits.pop(k, None)


def limit_general(request: Request) -> None:
    rate_limit(request, "general", RATE_LIMIT_GENERAL)


def limit_auth(request: Request) -> None:
    rate_limit(request, "auth", RATE_LIMIT_AUTH)


def limit_analyze(request: Request) -> None:
    rate_limit(request, "analyze", RATE_LIMIT_ANALYZE)


def limit_generate(request: Request) -> None:
    rate_limit(request, "generate", RATE_LIMIT_GENERATE)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> models.User:
    """Ignore any client-supplied user id header. Identity comes only from the JWT."""
    _ = x_user_id  # explicitly discarded
    rate_limit(request, "general", RATE_LIMIT_GENERAL)
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    request.state.access_token = creds.credentials
    return user
