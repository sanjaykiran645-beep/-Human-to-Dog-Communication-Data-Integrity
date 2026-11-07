"""Append-only audit events. No secrets, no raw audio."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from .. import models


def log(
    db: Session,
    *,
    action: str,
    entity: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        models.AuditEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action[:80],
            entity=entity[:40],
            entity_id=entity_id,
            detail=(detail or "")[:400] or None,
        )
    )
