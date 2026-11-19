"""Dog profile CRUD with Male/Female gender calibration and >10 FIFO auto-pruning (deletes oldest 3)."""

from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user
from ..services import audit
from ..services.breed_intelligence import resolve_breed_intelligence

router = APIRouter(prefix="/api/dogs", tags=["dogs"])

def _owned(db: Session, user: models.User, dog_id: str) -> models.Dog:
    dog = db.get(models.Dog, dog_id)
    if dog is None or dog.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    return dog

def _enrich_dog_silently(data: dict) -> dict:
    sex_val = (data.get("sex") or "male").strip().lower()
    if sex_val not in {"male", "female", "unknown"}:
        sex_val = "male"
    data["sex"] = sex_val

    intel = resolve_breed_intelligence(
        breed=data.get("breed"),
        weight_kg=data.get("weight_kg"),
        age_years=data.get("age_years"),
        fetch_remote=False,
        sex=sex_val,
    )
    if data.get("weight_kg") is None:
        base_w = float(intel.get("default_weight_kg", 20.0))
        if sex_val == "male":
            base_w = round(base_w * 1.08, 1)
        elif sex_val == "female":
            base_w = round(base_w * 0.92, 1)
        data["weight_kg"] = base_w
    return data


def _ensure_under_dog_limit(db: Session, user_id: str, limit: int = 10) -> None:
    count = len(list(db.scalars(select(models.Dog.id).where(models.Dog.user_id == user_id))))
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum of {limit} dog profiles per account reached. Delete an existing profile first.",
        )

@router.get("", response_model=list[schemas.DogOut])
def list_dogs(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[models.Dog]:
    return list(db.scalars(select(models.Dog).where(models.Dog.user_id == user.id).order_by(models.Dog.created_at.desc())))

@router.post("", response_model=schemas.DogOut, status_code=201)
def create_dog(payload: schemas.DogIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Dog:
    _ensure_under_dog_limit(db, user.id, limit=10)
    raw = _enrich_dog_silently(payload.model_dump())
    dog = models.Dog(id=str(uuid.uuid4()), user_id=user.id, **raw)
    db.add(dog)
    db.flush()
    audit.log(db, action="dog.create", entity="dog", user_id=user.id, entity_id=dog.id)
    db.commit()
    db.refresh(dog)
    return dog

@router.get("/{dog_id}", response_model=schemas.DogOut)
def get_dog(dog_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Dog:
    return _owned(db, user, dog_id)

@router.patch("/{dog_id}", response_model=schemas.DogOut)
def update_dog(dog_id: str, payload: schemas.DogIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Dog:
    dog = _owned(db, user, dog_id)
    raw = _enrich_dog_silently(payload.model_dump())
    for k, v in raw.items():
        setattr(dog, k, v)
    audit.log(db, action="dog.update", entity="dog", user_id=user.id, entity_id=dog.id)
    db.commit()
    db.refresh(dog)
    return dog

@router.delete("/{dog_id}")
def delete_dog(dog_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    dog = _owned(db, user, dog_id)
    db.delete(dog)
    audit.log(db, action="dog.delete", entity="dog", user_id=user.id, entity_id=dog_id)
    db.commit()
    return {"ok": True}
