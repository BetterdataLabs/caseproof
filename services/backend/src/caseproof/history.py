"""Revision, audit and outbox helpers. Every case mutation commits these in the same transaction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .actors import Actor
from .errors import NotFound, StaleRevision
from .models import AuditEvent, Case, Outbox


def utcnow() -> datetime:
    return datetime.now(UTC)


def lock_case(session: Session, case_id: uuid.UUID, expected_revision: int | None = None) -> Case:
    case = session.execute(select(Case).where(Case.id == case_id).with_for_update()).scalar_one_or_none()
    if case is None:
        raise NotFound("CASE_NOT_FOUND", "Case not found.")
    if expected_revision is not None and case.revision != expected_revision:
        raise StaleRevision(
            "STALE_REVISION",
            "The case changed since you loaded it. Review the updated evidence before resubmitting.",
            current_revision=case.revision,
        )
    return case


def bump(case: Case) -> int:
    case.revision += 1
    case.updated_at = utcnow()
    return case.revision


def record(
    session: Session,
    case: Case | None,
    event_type: str,
    actor: Actor,
    summary: str,
    *,
    reason: str = "",
    payload: dict[str, Any] | None = None,
    correlation_id: str = "",
    org_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        org_id=case.org_id if case else (org_id or actor.org_id),
        case_id=case.id if case else None,
        case_revision=case.revision if case else None,
        event_type=event_type,
        actor_type=actor.type,
        actor_id=actor.id,
        actor_name=actor.name,
        summary=summary,
        reason=reason,
        payload=payload or {},
        correlation_id=correlation_id,
    )
    session.add(event)
    return event


def emit(
    session: Session,
    org_id: uuid.UUID,
    event_type: str,
    *,
    case_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        Outbox(org_id=org_id, case_id=case_id, job_id=job_id, event_type=event_type, payload=payload or {})
    )
