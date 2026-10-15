"""Jobs, leases and the transactional outbox.

A job carries only ids. The database allows one queued and one leased agent job per case; a new event
coalesces into the queued job instead of creating parallel work. Leases use database time and fence every
agent mutation.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from .casework import org_controls
from .config import get_settings
from .errors import Conflict
from .history import emit, record, utcnow
from .models import Case, Job

WAKE_TRIGGERS = {
    "PolicyUpdated",
    "CaseCreated",
    "EvidenceReceived",
    "ReplyReceived",
    "HumanDecisionRecorded",
    "RecoveryRequested",
    "ReviewReopened",
    "ModeChanged",
    "DocumentChecksEnabled",
    "Continuation",
}


def enqueue_agent(session: Session, case: Case, trigger: str, detail: str = "") -> Job | None:
    """Record the obligation to run the agent. Returns None if automation cannot run for this case now."""
    assert trigger in WAKE_TRIGGERS, trigger
    if case.automation_mode == "off":
        return None
    if case.execution == "paused" and trigger != "RecoveryRequested":
        return None
    if not org_controls(session, case.org_id).automation_enabled:
        return None
    queued = session.execute(
        select(Job)
        .where(Job.case_id == case.id, Job.kind == "agent", Job.state == "queued")
        .with_for_update()
    ).scalar_one_or_none()
    if queued is not None:
        queued.input_revision = case.revision
        queued.trigger_detail = (queued.trigger_detail + f"; {trigger}: {detail}").strip("; ")[:2000]
        return queued
    job = Job(
        org_id=case.org_id,
        case_id=case.id,
        kind="agent",
        trigger=trigger,
        trigger_detail=detail[:2000],
        input_revision=case.revision,
    )
    session.add(job)
    session.flush()
    emit(
        session,
        case.org_id,
        "JobQueued",
        case_id=case.id,
        job_id=job.id,
        payload={"kind": "agent", "trigger": trigger},
    )
    if case.execution != "running":
        case.execution = "queued"
    case.next_action = "Agent queued: " + trigger_label(trigger)
    return job


def trigger_label(trigger: str) -> str:
    return {
        "CaseCreated": "inspect the new case",
        "EvidenceReceived": "process new evidence",
        "ReplyReceived": "process the business's reply",
        "HumanDecisionRecorded": "continue after the recorded decision",
        "RecoveryRequested": "resume after recovery",
        "ReviewReopened": "recheck after reopening",
        "ModeChanged": "re-evaluate after the automation mode changed",
        "DocumentChecksEnabled": "check document appearance against the selected options",
        "Continuation": "continue the previous run",
    }.get(trigger, trigger)


def lease(session: Session, job_id: uuid.UUID) -> tuple[Job | None, str]:
    """Acquire a lease for a queued job. Returns (job, status) where status explains a refusal."""
    settings = get_settings()
    job = session.execute(
        select(Job).where(Job.id == job_id).with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None:
        return None, "LOCKED_OR_MISSING"
    if job.state != "queued":
        return job, "DUPLICATE_DELIVERY"
    if job.next_eligible_at > utcnow():
        return job, "NOT_ELIGIBLE"
    if job.kind == "agent":
        active = session.execute(
            select(Job.id).where(Job.case_id == job.case_id, Job.kind == "agent", Job.state == "leased")
        ).first()
        if active:
            job.next_eligible_at = utcnow() + timedelta(seconds=2)
            job.deferrals += 1
            return job, "CASE_BUSY"
        org_running = session.execute(
            select(func.count()).where(Job.org_id == job.org_id, Job.kind == "agent", Job.state == "leased")
        ).scalar_one()
        if org_running >= settings.org_concurrency:
            job.next_eligible_at = utcnow() + timedelta(seconds=2)
            job.deferrals += 1  # capacity deferral does not consume a model allowance
            return job, "ORG_CAPACITY"
    job.state = "leased"
    job.lease_token = uuid.uuid4()
    job.attempt += 1
    job.started_at = utcnow()
    session.flush()
    session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(lease_expires_at=func.now() + text(f"interval '{settings.lease_seconds} seconds'"))
    )
    return job, "LEASED"


def lease_valid(session: Session, job_id: uuid.UUID, token: uuid.UUID) -> bool:
    row = session.execute(
        select(Job.state, Job.lease_token, Job.lease_expires_at > func.now())
        .where(Job.id == job_id)
        .with_for_update()
    ).first()
    return bool(row and row[0] == "leased" and row[1] == token and row[2])


def heartbeat(session: Session, job_id: uuid.UUID, token: uuid.UUID) -> bool:
    settings = get_settings()
    result = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.lease_token == token,
            Job.state == "leased",
            Job.lease_expires_at > func.now(),
        )
        .values(lease_expires_at=func.now() + text(f"interval '{settings.lease_seconds} seconds'"))
    )
    return result.rowcount == 1


def finish(session: Session, job_id: uuid.UUID, token: uuid.UUID, state: str, result: dict) -> bool:
    job = session.execute(select(Job).where(Job.id == job_id).with_for_update()).scalar_one_or_none()
    if job is None or job.lease_token != token or job.state != "leased":
        return False
    job.state = state
    job.result = result
    job.finished_at = utcnow()
    job.lease_token = None
    return True


def require_lease(session: Session, job_id: uuid.UUID, token: uuid.UUID) -> None:
    if not lease_valid(session, job_id, token):
        raise Conflict(
            "LEASE_LOST", "This worker attempt no longer holds the case lease; its result is not applied."
        )


def expire_leases(session: Session) -> list[Job]:
    """Reconciler: expired leases release the case. The work is retried from saved state."""
    expired = (
        session.execute(
            select(Job)
            .where(Job.state == "leased", Job.lease_expires_at < func.now())
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )
    for job in expired:
        job.state = "failed"
        job.result = {"reason": "LEASE_EXPIRED"}
        job.finished_at = utcnow()
    return list(expired)


def record_pause(session: Session, case: Case, actor, reason_code: str, summary: str) -> None:
    case.execution = "paused"
    case.paused_reason = reason_code
    case.next_action = summary
    record(session, case, "AutomationPaused", actor, summary, payload={"reason": reason_code})
