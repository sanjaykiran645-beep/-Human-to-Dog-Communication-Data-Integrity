"""Password hashing and JWT. No homemade cryptography."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status

from .config import ACCESS_TOKEN_MINUTES, SECRET_KEY

log = logging.getLogger("caninesense.security")

ALGORITHM = "HS256"
TOKEN_DENYLIST: dict[str, float] = {}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_token_revoked(token: str) -> bool:
    if token in TOKEN_DENYLIST:
        return True
    tok_hash = _token_hash(token)
    try:
        from . import models
        from .db import SessionLocal

        with SessionLocal() as session:
            row = session.get(models.RevokedToken, tok_hash)
            return row is not None
    except Exception:
        log.warning("Failed checking durable revoked_tokens table", exc_info=True)
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    if _is_token_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def revoke_token(token: str) -> None:
    now = datetime.now(timezone.utc).timestamp()
    exp = now + (ACCESS_TOKEN_MINUTES * 60)
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = float(payload.get("exp", exp))
    except Exception:
        pass
    TOKEN_DENYLIST[token] = exp
    if len(TOKEN_DENYLIST) > 5000:
        expired = [t for t, ex in list(TOKEN_DENYLIST.items()) if ex < now]
        for t in expired:
            TOKEN_DENYLIST.pop(t, None)
    tok_hash = _token_hash(token)
    try:
        from . import models
        from .db import SessionLocal

        with SessionLocal() as session:
            session.merge(models.RevokedToken(token_hash=tok_hash, expires_at=exp))
            session.query(models.RevokedToken).filter(models.RevokedToken.expires_at < now).delete()
            session.commit()
    except Exception:
        log.exception("Failed persisting revoked JWT to database")
