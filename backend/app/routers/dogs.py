"""Dog profile CRUD. All queries scoped to the authenticated user."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user
from ..services import audit

router = APIRouter(prefix="/api/dogs", tags=["dogs"])


def _owned(db: Session, user: models.User, dog_id: str) -> models.Dog:
    dog = db.get(models.Dog, dog_id)
    if dog is None or dog.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    return dog


@router.get("", response_model=list[schemas.DogOut])
def list_dogs(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[models.Dog]:
    return list(db.scalars(select(models.Dog).where(models.Dog.user_id == user.id).order_by(models.Dog.created_at.desc())))


@router.post("", response_model=schemas.DogOut, status_code=201)
def create_dog(
    payload: schemas.DogIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Dog:
    dog = models.Dog(id=str(uuid.uuid4()), user_id=user.id, **payload.model_dump())
    db.add(dog)
    db.flush()
    audit.log(db, action="dog.create", entity="dog", user_id=user.id, entity_id=dog.id)
    db.commit()
    return dog


@router.get("/{dog_id}", response_model=schemas.DogOut)
def get_dog(dog_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Dog:
    return _owned(db, user, dog_id)


@router.patch("/{dog_id}", response_model=schemas.DogOut)
def update_dog(
    dog_id: str,
    payload: schemas.DogIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Dog:
    dog = _owned(db, user, dog_id)
    for k, v in payload.model_dump().items():
        setattr(dog, k, v)
    audit.log(db, action="dog.update", entity="dog", user_id=user.id, entity_id=dog.id)
    db.commit()
    return dog


@router.delete("/{dog_id}")
def delete_dog(dog_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    dog = _owned(db, user, dog_id)
    db.delete(dog)
    audit.log(db, action="dog.delete", entity="dog", user_id=user.id, entity_id=dog_id)
    db.commit()
    return {"ok": True}
