"""Job execution: lease, bounded invocation, heartbeat and settlement.

Model and storage calls happen outside database transactions. The worker reads a snapshot, does bounded
external work, then validates its lease and expected revision before each effect. A stale result is
retained as a superseded attempt, not applied.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from ..actors import agent_actor
from ..casework import settle_execution
from ..config import get_settings
from ..db import global_session, org_session
from ..exports import render_export
from ..history import lock_case, record, utcnow
from ..jobs import finish, heartbeat, lease, lease_valid, record_pause
from ..models import AgentRun, Case, Export
from ..policies import settings_for
from ..tasks import open_task
from .agent import run_agent, wake_message
from .extract import process_uploads
from .gateway import BudgetExceeded, ModelUnavailable, RunContext
from .policy_review import process_policy_review
from .research import process_credit_research
from .rules import run_rules
from .tools import case_snapshot
from .visual import process_visual_reviews

log = logging.getLogger("caseproof.worker")


def route(job_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, str, str] | None:
    with global_session() as session:
        row = session.execute(
            text("SELECT org_id, case_id, kind, state FROM cp_job_route(:j)"), {"j": str(job_id)}
        ).first()
    return (row[0], row[1], row[2], row[3]) if row else None


async def execute_job(job_id: uuid.UUID, controller: str | None = None) -> dict[str, Any]:
    routed = route(job_id)
    if routed is None:
        return {"status": "UNKNOWN_JOB"}
    org_id, case_id, kind, state = routed
    if state != "queued":
        return {"status": "DUPLICATE_DELIVERY", "state": state}
    if kind == "export":
        return await asyncio.to_thread(_run_export, org_id, job_id)
    return await _run_agent_job(org_id, case_id, job_id, controller)


def _run_export(org_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
    with org_session(org_id) as session:
        job, status = lease(session, job_id)
        if status != "LEASED":
            return {"status": status}
        token = job.lease_token
        export_id = job.export_id
    try:
        with org_session(org_id) as session:
            export = session.get(Export, export_id)
            render_export(session, export)
            state = export.state
        with org_session(org_id) as session:
            finish(session, job_id, token, "done", {"export_state": state})
        return {"status": "DONE", "export_state": state}
    except Exception as exc:
        log.exception("export failed")
        with org_session(org_id) as session:
            export = session.get(Export, export_id)
            if export.attempts >= 3:
                export.state = "failed"
            finish(session, job_id, token, "failed", {"error": type(exc).__name__})
        return {"status": "FAILED"}


async def _run_agent_job(
    org_id: uuid.UUID, case_id: uuid.UUID, job_id: uuid.UUID, controller: str | None
) -> dict[str, Any]:
    settings = get_settings()
    controller = controller or ("rule-controller" if settings.model_provider == "rules" else "adk-gemini")
    with org_session(org_id) as session:
        job, status = lease(session, job_id)
        if status != "LEASED":
            return {"status": status}
        case = lock_case(session, case_id)
        token = job.lease_token
        trigger, detail = job.trigger, job.trigger_detail
        if case.execution == "paused" and trigger != "RecoveryRequested":
            finish(session, job_id, token, "cancelled", {"reason": "CASE_PAUSED"})
            return {"status": "CASE_PAUSED"}
        if case.automation_mode == "off":
            finish(session, job_id, token, "cancelled", {"reason": "AUTOMATION_OFF"})
            settle_execution(session, case)
            return {"status": "AUTOMATION_OFF"}
        policy_settings = settings_for(session, case)
        max_wakeups = policy_settings["automatic_wakeups_per_case"] + case.wakeup_extension
        if case.wakeups_used >= max_wakeups:
            _budget_task(
                session, case, "WAKEUP_LIMIT", f"The case used its {max_wakeups} automatic wake-ups."
            )
            finish(session, job_id, token, "done", {"reason": "WAKEUP_LIMIT"})
            return {"status": "WAKEUP_LIMIT"}
        if case.execution == "paused":
            case.execution = "idle"
            case.paused_reason = None
        case.wakeups_used += 1
        case.execution = "running"
        case.next_action = "Agent working"
        case.updated_at = utcnow()
        run = AgentRun(
            org_id=org_id,
            case_id=case_id,
            job_id=job_id,
            trigger=trigger,
            mode=case.automation_mode,
            controller=controller,
            model=settings.model_name if controller == "adk-gemini" else "",
            input_revision=case.revision,
        )
        session.add(run)
        session.flush()
        record(
            session,
            case,
            "AgentRunStarted",
            agent_actor(org_id, controller),
            f"Agent run started ({trigger})"
            + (" in shadow mode" if case.automation_mode == "shadow" else ""),
            payload={"run_id": str(run.id), "job_id": str(job_id), "controller": controller},
        )
        ctx = RunContext(
            org_id=org_id,
            case_id=case_id,
            job_id=job_id,
            lease_token=token,
            run_id=run.id,
            mode=case.automation_mode,
            controller=controller,
            expected_revision=case.revision,
            trigger=trigger,
            policy_settings=policy_settings,
        )
        snapshot = case_snapshot(session, case_id)

    beat = asyncio.create_task(_heartbeat(org_id, job_id, token))
    outcome, stop_reason, summary, failure = "no_action", "", "", None
    try:
        if await process_uploads(ctx):
            summary = "Uploaded documents processed; review continues from the saved evidence."
        elif await process_visual_reviews(ctx):
            summary = "Optional document appearance checks saved; review continues."
        elif await process_policy_review(ctx):
            summary = "Policy criteria assessed against the current documents; review continues."
        elif await process_credit_research(ctx):
            summary = "Public company research progress saved; review continues."
        elif controller == "adk-gemini":
            summary = await run_agent(ctx, wake_message(trigger, detail, snapshot))
        else:
            summary = await run_rules(ctx)
        outcome = ctx.terminal or "no_action"
        stop_reason = ctx.stop_reason
    except BudgetExceeded as exc:
        outcome, stop_reason, failure = "paused", exc.code, ("budget", exc)
    except ModelUnavailable as exc:
        outcome, stop_reason, failure = "paused", exc.code, ("model", exc)
    except Exception as exc:
        log.exception("agent run failed")
        outcome, stop_reason, failure = "paused", "WORKER_ERROR", ("error", exc)
    finally:
        beat.cancel()

    with org_session(org_id) as session:
        run = session.get(AgentRun, ctx.run_id)
        run.model_calls, run.tool_calls, run.retries = ctx.model_calls, ctx.tool_calls, ctx.retries
        run.input_tokens, run.output_tokens, run.cost_usd = (
            ctx.input_tokens,
            ctx.output_tokens,
            Decimal(ctx.cost_usd),
        )
        run.ended_at = utcnow()
        run.summary = (summary or "")[:2000]
        if not lease_valid(session, job_id, token):
            run.outcome, run.stop_reason = "stale", "LEASE_LOST"
            return {"status": "LEASE_LOST"}
        case = lock_case(session, case_id)
        if failure is not None:
            kind, exc = failure
            if kind == "budget":
                _budget_task(session, case, stop_reason, str(exc))
            else:
                _service_failure_task(session, case, stop_reason, str(exc))
        run.outcome, run.stop_reason, run.final_revision = outcome, stop_reason, case.revision
        finish(
            session,
            job_id,
            token,
            "done" if failure is None else "failed",
            {"outcome": outcome, "stop_reason": stop_reason},
        )
        session.flush()
        if case.execution == "running":
            case.execution = "idle"
        settle_execution(session, case)
        record(
            session,
            case,
            "AgentRunEnded",
            agent_actor(org_id, controller),
            f"Agent run ended: {outcome.replace('_', ' ')}" + (f" ({stop_reason})" if stop_reason else ""),
            payload={
                "run_id": str(run.id),
                "model_calls": ctx.model_calls,
                "tool_calls": ctx.tool_calls,
                "cost_usd": str(ctx.cost_usd),
            },
        )
    return {
        "status": "DONE",
        "outcome": outcome,
        "stop_reason": stop_reason,
        "model_calls": ctx.model_calls,
        "tool_calls": ctx.tool_calls,
    }


async def _heartbeat(org_id: uuid.UUID, job_id: uuid.UUID, token: uuid.UUID) -> None:
    interval = get_settings().heartbeat_seconds
    while True:
        await asyncio.sleep(interval)
        with org_session(org_id) as session:
            if not heartbeat(session, job_id, token):
                return


def _budget_task(session, case: Case, code: str, message: str) -> None:
    actor = agent_actor(case.org_id)
    record_pause(session, case, actor, code, f"Paused: {message}")
    open_task(
        session,
        case,
        actor,
        kind="budget_exhausted",
        requirement_keys=[],
        source_version_ids=[],
        observation_ids=[],
        passages=[],
        title="Automation allowance reached",
        question="The agent reached an operating limit. Grant a bounded extension, or keep the case on hold?",
        why_stopped=message,
        proposed_action="With an extension, the agent resumes from the saved case state.",
        dedupe_key=f"budget:{code}:{case.wakeups_used}",
    )


def _service_failure_task(session, case: Case, code: str, message: str) -> None:
    actor = agent_actor(case.org_id)
    record_pause(session, case, actor, code, f"Paused: {message}")
    open_task(
        session,
        case,
        actor,
        kind="service_failure",
        requirement_keys=[],
        source_version_ids=[],
        observation_ids=[],
        passages=[],
        title="Model service unavailable",
        question="The model service failed within the allowed retries. Completed checks are preserved and nothing "
        "was cleared. Resume automation, or keep the case on hold?",
        why_stopped=message,
        proposed_action="Resume when the service is available; the agent restarts from saved work.",
        dedupe_key=f"service:{code}:{case.wakeups_used}",
    )
