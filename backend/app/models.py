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


class StudyParticipant(Base):
    __tablename__ = "study_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dog_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("dogs.id", ondelete="SET NULL"), nullable=True)
    pseudonym: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    age_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    breed: Mapped[str | None] = mapped_column(String(80), nullable=True, default="unknown")
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True, default="unknown")
    hearing_limitations: Mapped[str | None] = mapped_column(String(120), nullable=True, default="none_reported")
    mobility_limitations: Mapped[str | None] = mapped_column(String(120), nullable=True, default="none_reported")
    familiarity_with_target_action: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    previous_cue_exposure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    training_history_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    baseline_behavioural_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    welfare_review_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExperimentalCue(Base):
    __tablename__ = "experimental_cues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cue_label: Mapped[str] = mapped_column(String(120), nullable=False)
    target_intention: Mapped[str] = mapped_column(String(40), nullable=False)
    target_action_description: Mapped[str] = mapped_column(Text, nullable=False)
    action_category: Mapped[str] = mapped_column(String(40), nullable=False)
    synthesis_method: Mapped[str] = mapped_column(String(60), nullable=False)
    synthesis_params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    peak_spl_dba: Mapped[float] = mapped_column(Float, nullable=False)
    f0_hz: Mapped[float] = mapped_column(Float, nullable=False)
    spectral_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    synth_version: Mapped[str] = mapped_column(String(80), nullable=False)
    cue_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TrialSchedule(Base):
    __tablename__ = "trial_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[str] = mapped_column(String(36), ForeignKey("study_participants.id", ondelete="CASCADE"), index=True)
    cue_id: Mapped[str] = mapped_column(String(36), ForeignKey("experimental_cues.id", ondelete="CASCADE"), index=True)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    randomization_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(60), default="latin_square_counterbalanced", nullable=False)
    planned_conditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BehaviouralTrial(Base):
    __tablename__ = "behavioural_trials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[str] = mapped_column(String(36), ForeignKey("study_participants.id", ondelete="CASCADE"), index=True)
    schedule_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trial_schedules.id", ondelete="SET NULL"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(60), nullable=False)
    trial_order_in_session: Mapped[int] = mapped_column(Integer, nullable=False)
    experimental_condition: Mapped[str] = mapped_column(String(60), nullable=False)
    cue_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("experimental_cues.id", ondelete="SET NULL"), nullable=True)
    pre_cue_state: Mapped[str] = mapped_column(String(40), nullable=False, default="resting")
    playback_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    measured_spl_dba: Mapped[float] = mapped_column(Float, nullable=False)
    handler_behaviour: Mapped[str] = mapped_column(String(60), default="neutral_standing_still", nullable=False)
    first_response: Mapped[str] = mapped_column(String(60), default="none", nullable=False)
    latency_to_orient_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_to_action_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_category: Mapped[str] = mapped_column(String(40), nullable=False)
    alternative_behaviour_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    reinforcement_provided: Mapped[str] = mapped_column(String(40), default="none", nullable=False)
    environmental_distractions: Mapped[str] = mapped_column(String(60), default="none", nullable=False)
    ambient_spl_dba: Mapped[float | None] = mapped_column(Float, nullable=True)
    video_reference_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    welfare_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    freezing_observed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    abort_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    abort_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    observer_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correction_audit_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TrialIndependentReview(Base):
    __tablename__ = "trial_independent_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trial_id: Mapped[str] = mapped_column(String(36), ForeignKey("behavioural_trials.id", ondelete="CASCADE"), index=True)
    reviewer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_blind_to_condition: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scored_outcome_category: Mapped[str] = mapped_column(String(40), nullable=False)
    scored_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    disagreement_with_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adjudicated_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    adjudicator_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

