-- Canonical SQLite schema. Applied by SQLAlchemy metadata.create_all (scripts/init_db.py).
-- This file is documentation. Do not paste secrets. Foreign keys must stay ON.

PRAGMA foreign_keys = ON;

-- users, dogs, recordings, analyses, generated_audio, dog_responses, audit_events
-- Ownership: every private row includes user_id; APIs filter by JWT subject, never by a client-supplied user id.
