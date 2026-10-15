"""Dispatcher and reconciler. No interpretation of document content or review decisions.

Delivers undelivered outbox records, recovers expired leases and missed deliveries, and applies due policy
timers (reminders and stop points). Locally it loops every few seconds; in the cloud, Cloud Scheduler calls
the reconcile endpoint once per minute.
"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import select

from .config import get_settings
from .db import dispatcher_engine, global_session, org_session
from .history import record, utcnow
from .jobs import enqueue_agent, expire_leases
from .models import Case, Job
from .queue import claim_outbox, deliver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("caseproof.dispatcher")
_last_delivery: dict[uuid.UUID, float] = {}


def reconcile_once() -> dict[str, int]:
    settings = get_settings()
    stats = {"delivered": 0, "redelivered": 0, "expired": 0, "timers": 0}
    engine = dispatcher_engine()
    with global_session(engine) as session:
        claimed = claim_outbox(session, limit=50)
    for _, job_id in claimed:
        if job_id and deliver(job_id):
            _last_delivery[job_id] = time.monotonic()
            stats["delivered"] += 1

    # Expired leases: release the case and resume from saved work (no duplicate request: unique intent keys).
    with global_session(engine) as session:
        expired = [(j.org_id, j.case_id, j.kind) for j in expire_leases(session)]
    for org_id, case_id, kind in expired:
        stats["expired"] += 1
        if kind != "agent":
            continue
        with org_session(org_id) as session:
            case = session.get(Case, case_id)
            from .actors import system_actor

            record(
                session,
                case,
                "LeaseExpired",
                system_actor(org_id, "Reconciler"),
                "A worker attempt stopped responding; resuming from saved work",
            )
            if case.execution == "running":
                case.execution = "idle"
            enqueue_agent(session, case, "Continuation", "worker lease expired")

    # Queued jobs whose delivery was lost (or deferred for capacity) are delivered again.
    now = time.monotonic()
    with global_session(engine) as session:
        running = session.execute(select(Job.id).where(Job.state == "leased", Job.kind == "agent")).all()
        queued = session.execute(
            select(Job.id, Job.created_at)
            .where(Job.state == "queued", Job.next_eligible_at <= utcnow())
            .order_by(Job.created_at)
            .limit(50)
        ).all()
    slots = max(0, settings.global_concurrency - len(running))
    for job_id, _ in queued:
        if now - _last_delivery.get(job_id, 0) < 6 or slots <= 0:
            continue
        if deliver(job_id):
            _last_delivery[job_id] = now
            stats["redelivered"] += 1
            slots -= 1

    # Due policy timers. Timers never call the model.
    from .casework import settle_execution
    from .requests import due_timer_effects, pending_timer_cases

    with global_session(engine) as session:
        due = pending_timer_cases(session)
    for org_id, case_id in due:
        with org_session(org_id) as session:
            from .history import lock_case

            case = lock_case(session, case_id)
            if due_timer_effects(session, case):
                stats["timers"] += 1
                settle_execution(session, case)
    return stats


def main() -> None:
    settings = get_settings()
    log.info(
        "dispatcher started (queue=%s, interval=%.1fs)", settings.queue_backend, settings.reconcile_interval_s
    )
    while True:
        try:
            stats = reconcile_once()
            if any(stats.values()):
                log.info("reconcile %s", stats)
        except Exception:
            log.exception("reconcile failed; retrying")
        time.sleep(settings.reconcile_interval_s)


if __name__ == "__main__":
    main()
