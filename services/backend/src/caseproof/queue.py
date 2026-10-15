"""Job delivery adapters. Delivery is neither ordered nor exactly once; the database decides what runs."""

from __future__ import annotations

import logging
import threading
import uuid

import httpx
from sqlalchemy import select, update

from .config import get_settings
from .models import Outbox
from .policies import MAX_RUN_SECONDS

log = logging.getLogger("caseproof.queue")


def deliver(job_id: uuid.UUID) -> bool:
    settings = get_settings()
    if settings.queue_backend == "cloudtasks":
        return _cloud_tasks(job_id)
    try:
        response = httpx.post(
            f"{settings.worker_url}/jobs/execute",
            json={"job_id": str(job_id), "mode": "async"},
            headers={"Authorization": f"Bearer {settings.internal_token}"},
            timeout=3.0,
        )
        return response.status_code < 500
    except httpx.HTTPError as exc:
        log.warning("job delivery failed: %s", type(exc).__name__)
        return False


def _cloud_tasks(job_id: uuid.UUID) -> bool:
    from google.cloud import tasks_v2

    settings = get_settings()
    client = tasks_v2.CloudTasksClient()
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{settings.worker_url}/jobs/execute",
            headers={"Content-Type": "application/json"},
            body=f'{{"job_id": "{job_id}"}}'.encode(),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=settings.cloud_tasks_service_account, audience=settings.worker_url
            ),
        ),
        dispatch_deadline={"seconds": MAX_RUN_SECONDS + 30},
    )
    client.create_task(parent=settings.cloud_tasks_queue, task=task)
    return True


def claim_outbox(session, limit: int = 20) -> list[tuple[int, uuid.UUID | None]]:
    """Atomically claim undelivered JobQueued events."""
    rows = session.execute(
        select(Outbox.id, Outbox.job_id)
        .where(Outbox.dispatched_at.is_(None), Outbox.event_type == "JobQueued")
        .order_by(Outbox.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    if rows:
        from .history import utcnow

        session.execute(
            update(Outbox)
            .where(Outbox.id.in_([r[0] for r in rows]))
            .values(dispatched_at=utcnow(), attempts=Outbox.attempts + 1)
        )
    return [(r[0], r[1]) for r in rows]


def prompt_dispatch(org_id: uuid.UUID) -> None:
    """After a command commits, try to deliver its jobs immediately; the reconciler covers any miss."""

    def run() -> None:
        from .db import org_session

        try:
            with org_session(org_id) as session:
                claimed = claim_outbox(session)
            for _, job_id in claimed:
                if job_id:
                    deliver(job_id)
        except Exception:
            log.exception("prompt dispatch failed; reconciler will retry")

    threading.Thread(target=run, daemon=True).start()
