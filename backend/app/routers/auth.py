"""Authentication routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user, limit_auth
from ..security import create_access_token, hash_password, revoke_token, verify_password
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
_DUMMY_HASH = hash_password("caninesense-timing-equalizer")


@router.post("/register", response_model=schemas.TokenOut)
def register(payload: schemas.RegisterIn, request: Request, db: Session = Depends(get_db)) -> schemas.TokenOut:
    limit_auth(request)
    email = payload.email.lower().strip()
    existing = db.scalar(select(models.User).where(models.User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = models.User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
    )
    db.add(user)
    db.flush()
    audit.log(db, action="user.register", entity="user", user_id=user.id, entity_id=user.id)
    db.commit()
    token = create_access_token(user.id, user.email)
    return schemas.TokenOut(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, request: Request, db: Session = Depends(get_db)) -> schemas.TokenOut:
    limit_auth(request)
    email = payload.email.lower().strip()
    user = db.scalar(select(models.User).where(models.User.email == email))
    # Always run one bcrypt comparison so response time does not reveal whether the email exists.
    stored_hash = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(payload.password, stored_hash)
    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    audit.log(db, action="user.login", entity="user", user_id=user.id, entity_id=user.id)
    db.commit()
    token = create_access_token(user.id, user.email)
    return schemas.TokenOut(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/logout")
def logout(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    token = getattr(request.state, "access_token", None)
    if token:
        revoke_token(token)
    audit.log(db, action="user.logout", entity="user", user_id=user.id, entity_id=user.id)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)) -> models.User:
    return user


@router.post("/change-password")
def change_password(
    payload: schemas.ChangePasswordIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    audit.log(db, action="user.password_change", entity="user", user_id=user.id, entity_id=user.id)
    db.commit()
    return {"ok": True}
