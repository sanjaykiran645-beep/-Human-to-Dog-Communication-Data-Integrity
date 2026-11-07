"""Request and response schemas. Keep API contracts explicit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name required")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DogIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    sex: str | None = Field(default=None, max_length=16)
    age_years: float | None = Field(default=None, ge=0, le=40)
    weight_kg: float | None = Field(default=None, ge=0.2, le=120)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name required")
        return v

    @field_validator("sex")
    @classmethod
    def sex_ok(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.lower().strip()
        if v not in {"female", "male", "unknown"}:
            raise ValueError("sex must be female, male, or unknown")
        return v


class DogOut(BaseModel):
    id: str
    user_id: str
    name: str
    breed: str | None
    sex: str | None
    age_years: float | None
    weight_kg: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntentIn(BaseModel):
    text: str = Field(default="", max_length=500)
    dog_id: str | None = None
    intent_override: str | None = None
    vocalization_target: str | None = None
    generation_method: str | None = Field(default="reference_direct", max_length=40)
    reference_asset_id: str | None = Field(default=None, max_length=80)
    intensity: float | None = Field(default=None, ge=0.15, le=1.0)
    duration_sec: float | None = Field(default=None, ge=0.08, le=6.0)
    pitch_hz: float | None = Field(default=None, ge=60, le=2000)


class GenerateIn(BaseModel):
    text: str = Field(default="", max_length=500)
    dog_id: str | None = None
    intent_override: str | None = None
    vocalization_target: str | None = None
    generation_method: str | None = Field(default="reference_direct", max_length=40)
    reference_asset_id: str | None = Field(default=None, max_length=80)
    intensity: float | None = Field(default=None, ge=0.15, le=1.0)
    duration_sec: float | None = Field(default=None, ge=0.08, le=6.0)
    pitch_hz: float | None = Field(default=None, ge=60, le=2000)
    pitch_shift_semitones: float | None = Field(default=None, ge=-2.0, le=2.0)
    time_stretch_rate: float | None = Field(default=None, ge=0.85, le=1.18)
    variation_index: int = Field(default=0, ge=0, le=100)
    idempotency_key: str | None = Field(default=None, max_length=120)


class ReferenceAnnotationUpdateIn(BaseModel):
    confirmed_category: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=500)


class GenerationFeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    sounds_natural: bool = True
    notes: str | None = Field(default=None, max_length=500)


class BlindListeningSubmissionIn(BaseModel):
    sample_id: str = Field(min_length=1, max_length=80)
    reviewer_id: str = Field(default="independent_reviewer_1", max_length=80)
    sounds_like_genuine_dog: bool
    perceived_category: str = Field(min_length=1, max_length=32)
    naturalness_score: int = Field(ge=1, le=5)
    artifact_severity_score: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=500)


class HealthOut(BaseModel):
    status: str
    version: str
    vocalization_model: str
    behavior_model: str
    synth_model: str
    accuracy_target_met: bool
    notes: str


class ErrorOut(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] | None = None
