"""Relational schema. Every user-owned row carries user_id for authorization."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    dogs: Mapped[list["Dog"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped[User] = relationship(back_populates="dogs")


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dog_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("dogs.id", ondelete="SET NULL"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    spectrogram_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    waveform_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analysis: Mapped["Analysis | None"] = relationship(back_populates="recording", uselist=False)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recording_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recordings.id", ondelete="CASCADE"), unique=True, index=True
    )
    dog_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("dogs.id", ondelete="SET NULL"), nullable=True)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    behavior_model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    vocalization: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    probabilities_json: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_json: Mapped[str] = mapped_column(Text, nullable=False)
    features_json: Mapped[str] = mapped_column(Text, nullable=False)
    behavior_json: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_json: Mapped[str] = mapped_column(Text, nullable=False)
    limitations_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    recording: Mapped[Recording] = relationship(back_populates="analysis")


class GeneratedAudio(Base):
    __tablename__ = "generated_audio"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dog_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("dogs.id", ondelete="SET NULL"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    intent_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False)
    vocalization_target: Mapped[str] = mapped_column(String(32), nullable=False)
    synth_version: Mapped[str] = mapped_column(String(80), nullable=False)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DogResponse(Base):
    __tablename__ = "dog_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    generated_id: Mapped[str] = mapped_column(String(36), ForeignKey("generated_audio.id", ondelete="CASCADE"), index=True)
    recording_id: Mapped[str] = mapped_column(String(36), ForeignKey("recordings.id", ondelete="CASCADE"))
    analysis_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("generated_id", "recording_id", name="uq_response_pair"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
