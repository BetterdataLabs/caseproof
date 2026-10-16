"""Case lifecycle: creation, question results, completion, reopening and execution status.

Completion recomputes every prerequisite inside its transaction.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import catalog
from .actors import Actor
from .checks import CHECKS_VERSION, CheckResult, ClaimView, PartyView, evaluate
from .document_checks import eligible
from .errors import Conflict, NotFound, Unsupported
from .evidence import ingest_pdf, ingest_written_message, version_views
from .history import bump, emit, record, utcnow
from .models import (
    Case,
    DocumentVersion,
    Export,
    HumanTask,
    InfoRequest,
    Job,
    MaterialClaim,
    OrgControl,
    PolicyVersion,
    Question,
    Reply,
    RequestItem,
)
from .policies import definition_for
from .policy_checks import combine_checks, sync_review_tasks

OPEN_TASK_STATES = ("pending", "claimed")


def policy_of(session: Session, case: Case) -> PolicyVersion:
    policy = session.get(PolicyVersion, case.policy_id)
    if policy is None:
        raise NotFound("POLICY_NOT_FOUND", "Policy not found.")
    return policy


def parties_of(case: Case) -> PartyView:
    return PartyView(
        seller=case.seller["name"],
        buyer=case.buyer["name"],
        receipt_issuers=[p["name"] for p in case.permitted_receipt_issuers],
        invoice_reference=case.invoice_reference,
    )


def claims_of(session: Session, case_id: uuid.UUID) -> list[MaterialClaim]:
    return list(
        session.execute(
            select(MaterialClaim).where(MaterialClaim.case_id == case_id).order_by(MaterialClaim.created_at)
        ).scalars()
    )


def compute_checks(session: Session, case: Case) -> dict[str, CheckResult]:
    claims = [
        ClaimView(str(c.id), c.requirement_key, c.status, c.conditions) for c in claims_of(session, case.id)
    ]
    baseline = (
        {}
        if case.scenario_key == "uploaded"
        else evaluate(parties_of(case), version_views(session, case.id), claims)
    )
    return combine_checks(session, case, baseline)


def questions_of(session: Session, case_id: uuid.UUID) -> dict[str, Question]:
    rows = session.execute(select(Question).where(Question.case_id == case_id)).scalars()
    return {q.requirement_key: q for q in rows}


def open_tasks(session: Session, case_id: uuid.UUID) -> list[HumanTask]:
    return list(
        session.execute(
            select(HumanTask).where(HumanTask.case_id == case_id, HumanTask.state.in_(OPEN_TASK_STATES))
        ).scalars()
    )


def outstanding_requests(session: Session, case_id: uuid.UUID) -> list[InfoRequest]:
    return list(
        session.execute(
            select(InfoRequest).where(InfoRequest.case_id == case_id, InfoRequest.state == "issued")
        ).scalars()
    )


def outstanding_question_ids(session: Session, case_id: uuid.UUID) -> set[uuid.UUID]:
    rows = session.execute(
        select(RequestItem.question_id)
        .join(InfoRequest, InfoRequest.id == RequestItem.request_id)
        .where(
            InfoRequest.case_id == case_id,
            InfoRequest.state == "issued",
            InfoRequest.stop_reached_at.is_(None),
            RequestItem.status.in_(("outstanding", "progress")),
        )
    ).scalars()
    return set(rows)


def apply_checks(session: Session, case: Case, actor: Actor, *, resolve: bool) -> dict[str, CheckResult]:
    """Store deterministic results. Only `resolve=True` (run_checks / completion service) may resolve a question;
    evidence ingestion can only invalidate."""
    results = compute_checks(session, case)
    sync_review_tasks(session, case, actor)
    questions = questions_of(session, case.id)
    tasks = open_tasks(session, case.id)
    blocked_keys = {k for t in tasks for k in t.requirement_keys}
    requested = outstanding_question_ids(session, case.id)
    retained = {c.requirement_key for c in claims_of(session, case.id) if c.status == "retained"}
    for key, result in results.items():
        q = questions[key]
        deps_changed = sorted(q.evidence_refs or []) != sorted(result.evidence_refs)
        was_resolved = q.state == "resolved"
        q.check_result = result.result
        q.reason_code = result.reason_code
        q.detail = result.detail
        q.metrics = result.metrics
        q.updated_at = utcnow()
        q.checked_revision = case.revision
        can_close = (
            result.result == "pass"
            and key not in blocked_keys
            and (key not in retained or result.satisfied_claims)
        )
        if was_resolved and can_close:
            if deps_changed:
                record(
                    session,
                    case,
                    "QuestionRevalidated",
                    actor,
                    f"Rechecked after an evidence change: {q.label} still holds",
                    reason=result.detail,
                    payload={"requirement": key, "evidence": result.evidence_refs},
                )
            q.evidence_refs = result.evidence_refs
            continue
        q.evidence_refs = result.evidence_refs
        if result.reason_code == "CONDITIONS_NOT_MET":
            # The requested correction arrived but does not meet the recorded conditions: the request was
            # answered, unsatisfactorily. The question now needs a reviewer, not another automatic request.
            for item in session.execute(
                select(RequestItem).where(
                    RequestItem.question_id == q.id, RequestItem.status.in_(("outstanding", "progress"))
                )
            ).scalars():
                item.status = "closed"
                item.progress_note = (
                    "Correction received but it does not meet the reviewer's recorded conditions."
                )
        if resolve and can_close:
            q.state = "resolved"
            q.resolved_at = utcnow()
            q.resolved_revision = case.revision
            q.resolved_by = actor.type
            for claim in claims_of(session, case.id):
                if str(claim.id) in result.satisfied_claims:
                    claim.status = "satisfied"
                    claim.satisfied_revision = case.revision
            for item in session.execute(
                select(RequestItem).where(
                    RequestItem.question_id == q.id, RequestItem.status.in_(("outstanding", "progress"))
                )
            ).scalars():
                item.status = "answered"
            record(
                session,
                case,
                "QuestionResolved",
                actor,
                f"Resolved: {q.label}",
                reason=result.detail,
                payload={
                    "requirement": key,
                    "evidence": result.evidence_refs,
                    "checks_version": CHECKS_VERSION,
                },
            )
            continue
        if was_resolved:
            record(
                session,
                case,
                "QuestionReopened",
                actor,
                f"Reopened: {q.label}",
                reason=result.detail,
                payload={"requirement": key},
            )
        q.resolved_at = None
        q.resolved_revision = None
        q.resolved_by = None
        if key in blocked_keys:
            q.state = "waiting_decision"
        elif q.id in requested:
            q.state = "waiting_evidence"
        else:
            q.state = "open"
    _close_answered_requests(session, case)
    _supersede_obsolete_tasks(session, case, actor, results)
    rejected_replacements = [
        key for key, result in results.items() if result.reason_code == "REPLACEMENT_REJECTED"
    ]
    if rejected_replacements:
        from .tasks import open_task

        existing_keys = {key for task in open_tasks(session, case.id) for key in task.requirement_keys}
        decided_sources = {
            source
            for task in session.execute(
                select(HumanTask).where(
                    HumanTask.case_id == case.id,
                    HumanTask.kind == "evidence_problem",
                    HumanTask.state == "decided",
                )
            ).scalars()
            for source in task.source_version_ids
        }
        for key in rejected_replacements:
            if key in existing_keys:
                continue
            role = "invoice" if key == "invoice_total" else "delivery_receipt"
            rejected = list(
                session.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.case_id == case.id,
                        DocumentVersion.source_role == role,
                        DocumentVersion.state == "rejected",
                        DocumentVersion.coverage == "blocking",
                    )
                ).scalars()
            )
            rejected = [version for version in rejected if str(version.id) not in decided_sources]
            if not rejected:
                continue
            open_task(
                session,
                case,
                actor,
                kind="evidence_problem",
                requirement_keys=[key],
                source_version_ids=[str(v.id) for v in rejected],
                observation_ids=[],
                passages=[],
                title="A replacement changes fields outside the policy",
                question="Should another request seek a correction within the original transaction, or should the case stay on hold?",
                why_stopped=results[key].detail,
                proposed_action="Keep the original transaction unchanged and authorise a request for a permitted correction.",
                dedupe_key=f"evidence_problem:{key}",
            )
    if case.scenario_key == "uploaded" or all(result.result == "pass" for result in results.values()):
        _review_unused_rejections(session, case, actor)
    return results


def _review_unused_rejections(session: Session, case: Case, actor: Actor) -> None:
    """Let a reviewer disposition rejected uploads without overriding the checklist first."""
    from .tasks import open_task

    if case.paused_reason == "ON_HOLD":
        return
    rejected = list(
        session.execute(
            select(DocumentVersion).where(
                DocumentVersion.case_id == case.id,
                DocumentVersion.state == "rejected",
                DocumentVersion.coverage == "blocking",
            )
        ).scalars()
    )
    for version in rejected:
        open_task(
            session,
            case,
            actor,
            kind="document_rejection",
            requirement_keys=[],
            source_version_ids=[str(version.id)],
            observation_ids=[],
            passages=[],
            title=f"Review unused rejected document: {version.label}",
            question=f"Is {version.label} unnecessary for this review? Excluding it reruns the checklist using the remaining evidence; it does not satisfy any requirement.",
            why_stopped=version.reject_detail or "This file could not be accepted as evidence.",
            proposed_action="Inspect the attachment and record why it is unnecessary, or keep it on hold. An excluded file stays in history; missing evidence still needs to be supplied.",
            dedupe_key=f"unused-rejection:{version.id}",
        )
    ids = {str(v.id) for v in rejected}
    for task in open_tasks(session, case.id):
        if (
            task.kind == "evidence_problem"
            and task.source_version_ids
            and set(task.source_version_ids) <= ids
        ):
            task.state = "superseded"
            record(
                session,
                case,
                "HumanTaskSuperseded",
                actor,
                f"Replaced with a document-exclusion decision: {task.title}",
                payload={"task_id": str(task.id)},
            )


def _supersede_obsolete_tasks(
    session: Session, case: Case, actor: Actor, results: dict[str, CheckResult]
) -> None:
    """An evidence-problem task whose questions now pass on current evidence no longer asks anything.
    Tasks covering written messages are never superseded this way: free text always needs a disposition."""
    from .document_checks import supersede_review_tasks

    supersede_review_tasks(session, case, actor)
    for task in open_tasks(session, case.id):
        if task.kind != "evidence_problem" or not task.requirement_keys:
            continue
        if all(results.get(k) and results[k].result == "pass" for k in task.requirement_keys):
            task.state = "superseded"
            record(
                session,
                case,
                "HumanTaskSuperseded",
                actor,
                f"Task no longer needed: {task.title}",
                reason="The affected checks now pass on current evidence.",
                payload={"task_id": str(task.id)},
            )
            for q in questions_of(session, case.id).values():
                if q.requirement_key in task.requirement_keys and q.state == "waiting_decision":
                    q.state = "open"


def _close_answered_requests(session: Session, case: Case) -> None:
    for request in outstanding_requests(session, case.id):
        items = (
            session.execute(select(RequestItem).where(RequestItem.request_id == request.id)).scalars().all()
        )
        if items and all(i.status in ("answered", "closed", "discarded") for i in items):
            request.state = "answered"


# creation


def next_reference(session: Session, org_id: uuid.UUID) -> str:
    count = session.execute(select(Case.id).where(Case.org_id == org_id)).all()
    return f"CP-{2026}-{len(count) + 1:04d}"


def create_case(
    session: Session,
    actor: Actor,
    *,
    policy: PolicyVersion,
    scenario_key: str,
    assigned_to: uuid.UUID | None,
    automation_mode: str,
) -> Case:
    if policy.status != "published":
        raise Conflict("POLICY_NOT_PUBLISHED", "Cases can only be created under a published policy version.")
    if automation_mode not in ("off", "shadow", "autonomous"):
        raise Unsupported("INVALID_MODE", "Automation mode must be off, shadow or autonomous.")
    try:
        sc = catalog.scenario(scenario_key)
    except KeyError as exc:
        raise Unsupported("UNKNOWN_FIXTURE", "Only predefined fictional fixtures are accepted.") from exc
    parties = catalog.parties()
    seller = {"key": sc["seller"], **parties[sc["seller"]]}
    buyer = {"key": sc["buyer"], **parties[sc["buyer"]]}
    case = Case(
        org_id=actor.org_id,
        reference=next_reference(session, actor.org_id),
        title=sc["title"],
        policy_id=policy.id,
        scenario_key=scenario_key,
        seller=seller,
        buyer=buyer,
        permitted_receipt_issuers=[{"key": k, **parties[k]} for k in sc["receipt_issuers"]],
        invoice_reference=sc["invoice_reference"],
        facility_reference=sc.get("facility_reference", ""),
        assigned_to=assigned_to,
        automation_mode=automation_mode,
        budget_usd=Decimal(str(definition_for(policy)["limits"]["case_budget_usd"])),
        created_by=actor.user_id,
        revision=1,
        execution="idle",
        expires_at=utcnow() + timedelta(days=30),
    )
    session.add(case)
    session.flush()
    for req in policy.definition["requirements"]:
        session.add(
            Question(org_id=case.org_id, case_id=case.id, requirement_key=req["key"], label=req["label"])
        )
    session.flush()
    record(
        session,
        case,
        "CaseCreated",
        actor,
        f"Case {case.reference} created for {seller['name']} — invoice {case.invoice_reference}",
        payload={
            "policy": f"{policy.key}/v{policy.version}",
            "fixture": scenario_key,
            "mode": automation_mode,
        },
    )
    for doc in sc["initial"]:
        if doc["role"] == "written_message":
            ingest_written_message(
                session,
                case,
                actor,
                text=doc["text"],
                attributed_to=doc.get("attributed_to", ""),
                received_via="initial",
                reply_id=None,
                fixture_key=doc["key"],
                policy=policy.definition,
            )
        else:
            ingest_pdf(
                session,
                case,
                actor,
                role=doc["role"],
                data=catalog.fixture_bytes(doc),
                declared_issuer=doc["declared_issuer"],
                received_via="initial",
                fixture_key=doc["key"],
                policy=policy.definition,
            )
    bump(case)
    apply_checks(session, case, actor, resolve=False)
    case.next_action = "Agent will inspect the documents" if automation_mode != "off" else "Manual review"
    return case


# completion


def completion_blockers(
    session: Session, case: Case, results: dict[str, CheckResult] | None = None
) -> list[dict[str, str]]:
    results = results or compute_checks(session, case)
    blockers: list[dict[str, str]] = []
    if (case.credit_research or {}).get("status") in {"pending", "researching"}:
        blockers.append(
            {
                "code": "CREDIT_RESEARCH_PENDING",
                "detail": "Optional company research is still being prepared for the report.",
            }
        )
    questions = questions_of(session, case.id)
    for key, result in results.items():
        if result.result != "pass":
            blockers.append(
                {
                    "code": result.reason_code,
                    "detail": f"{questions[key].label}: {result.detail}",
                    "kind": "check",
                }
            )
    for task in open_tasks(session, case.id):
        blockers.append({"code": "HUMAN_TASK_OPEN", "detail": f"Decision pending: {task.title}"})
    versions = (
        session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.case_id == case.id)
            .order_by(DocumentVersion.sequence)
        )
        .scalars()
        .all()
    )
    for v in versions:
        if eligible(v) and (v.visual_review or {}).get("status") in {"pending", "review_required"}:
            blockers.append(
                {
                    "code": "DOCUMENT_APPEARANCE_REVIEW",
                    "detail": f"{v.label}: optional document checks are pending or require a recorded appearance review.",
                }
            )
        if v.state in ("received", "validating"):
            blockers.append({"code": "EVIDENCE_PROCESSING", "detail": f"{v.label} is still being validated."})
        elif v.coverage == "needs_review":
            blockers.append(
                {
                    "code": "UNREVIEWED_MESSAGE",
                    "detail": f"{v.label} is a written message without a recorded human disposition.",
                }
            )
        elif v.coverage == "blocking":
            blockers.append(
                {"code": "UNSUPPORTED_SOURCE", "detail": f"{v.label} could not be used: {v.reject_detail}"}
            )
        elif v.coverage == "pending":
            blockers.append({"code": "SOURCE_NOT_ASSESSED", "detail": f"{v.label} has not been assessed."})
    retained = [c for c in claims_of(session, case.id) if c.status == "retained"]
    reported = {b["code"] for b in blockers}
    for claim in retained:
        satisfied = any(str(claim.id) in r.satisfied_claims for r in results.values())
        if not satisfied and "DISPUTE_RETAINED" not in reported and "CONDITIONS_NOT_MET" not in reported:
            blockers.append({"code": "DISPUTE_RETAINED", "detail": f"Retained dispute: {claim.statement}"})
    policy = policy_of(session, case)
    if policy.status != "published":
        blockers.append(
            {"code": "POLICY_NOT_CURRENT", "detail": "The case policy version is no longer published."}
        )
    return blockers


def try_complete(
    session: Session, case: Case, actor: Actor
) -> tuple[bool, list[dict[str, str]], Export | None]:
    if case.lifecycle == "complete":
        return True, [], session.get(Export, case.current_export_id) if case.current_export_id else None
    results = apply_checks(session, case, actor, resolve=True)
    blockers = completion_blockers(session, case, results)
    questions = questions_of(session, case.id)
    unresolved = [q for key, q in questions.items() if key in results and q.state != "resolved"]
    if unresolved and not blockers:
        blockers = [{"code": "QUESTION_OPEN", "detail": f"{q.label} is not resolved."} for q in unresolved]
    if blockers:
        return False, blockers, None
    for reply in session.execute(
        select(Reply).where(Reply.case_id == case.id, Reply.processed_revision.is_(None))
    ).scalars():
        reply.processed_revision = case.revision
    bump(case)
    case.lifecycle = "complete"
    case.completed_at = utcnow()
    case.next_action = "Review summary ready for the bank's financing process"
    case.next_event_at = None
    export = freeze_export(session, case, actor)
    record(
        session,
        case,
        "ReviewCompleted",
        actor,
        f"Document review complete at revision {case.revision}; summary {export.export_ref} prepared",
        payload={"export_id": str(export.id), "export_ref": export.export_ref},
    )
    return True, [], export


def freeze_export(session: Session, case: Case, actor: Actor) -> Export:
    from .exports import build_snapshot  # local import: exports depends on casework views

    snapshot = build_snapshot(session, case)
    policy = policy_of(session, case)
    export = Export(
        org_id=case.org_id,
        case_id=case.id,
        export_ref=f"EXP-{secrets.token_hex(4).upper()}",
        case_revision=case.revision,
        policy_label=f"{policy.key} v{policy.version}",
        state="preparing",
        snapshot=snapshot,
    )
    session.add(export)
    session.flush()
    case.current_export_id = export.id
    job = Job(
        org_id=case.org_id,
        case_id=case.id,
        kind="export",
        trigger="ExportRequested",
        input_revision=case.revision,
        export_id=export.id,
    )
    session.add(job)
    session.flush()
    emit(session, case.org_id, "JobQueued", case_id=case.id, job_id=job.id, payload={"kind": "export"})
    return export


def reopen_if_complete(session: Session, case: Case, actor: Actor, reason: str) -> bool:
    if case.lifecycle != "complete":
        return False
    case.lifecycle = "open"
    case.completed_at = None
    if case.current_export_id:
        export = session.get(Export, case.current_export_id)
        if export and export.state != "superseded":
            export.state = "superseded"
            export.superseded_at = utcnow()
            export.superseded_reason = reason
    record(session, case, "ReviewReopened", actor, f"Review reopened: {reason}", reason=reason)
    return True


# execution status


def org_controls(session: Session, org_id: uuid.UUID) -> OrgControl:
    control = session.get(OrgControl, org_id)
    if control is None:
        control = OrgControl(org_id=org_id, revision=1, automation_enabled=True)
        session.add(control)
        session.flush()
    return control


def settle_execution(session: Session, case: Case) -> None:
    """Derive the waiting state from saved work. Never hides a human task behind other processing."""
    if case.execution == "paused":
        return
    queued = session.execute(
        select(Job.id).where(Job.case_id == case.id, Job.kind == "agent", Job.state.in_(("queued", "leased")))
    ).first()
    if queued:
        case.execution = "queued" if case.execution != "running" else "running"
        return
    tasks = open_tasks(session, case.id)
    requests = outstanding_requests(session, case.id)
    if case.lifecycle == "complete":
        case.execution = "idle"
        case.next_event_at = None
    elif tasks:
        case.execution = "waiting_decision"
        case.next_action = f"Needs a decision: {tasks[0].title}"
        case.next_event_at = None
    elif requests:
        case.execution = "waiting_evidence"
        due = [r.stop_due_at if r.reminder_sent_at else r.reminder_due_at for r in requests]
        due = [d for d in due if d]
        case.next_event_at = min(due) if due else None
        reminder_pending = any(r.reminder_sent_at is None for r in requests)
        case.next_action = (
            "Waiting for the business to reply; reminder scheduled"
            if reminder_pending
            else "Waiting for the business to reply; reviewer stop point scheduled"
        )
    else:
        case.execution = "idle"
        if case.automation_mode == "off":
            case.next_action = "Manual review: automation is off for this case"
    case.updated_at = utcnow()


def case_primary_status(case: Case, tasks: list[HumanTask]) -> dict[str, Any]:
    if case.lifecycle == "complete":
        return {"key": "complete", "label": "Document review complete"}
    if case.execution == "paused":
        return {"key": "paused", "label": "Paused"}
    if tasks or case.execution == "waiting_decision":
        return {"key": "needs_decision", "label": "Needs a decision"}
    if case.execution in ("queued", "running"):
        return {"key": "working", "label": "Agent working"}
    if case.execution == "waiting_evidence":
        return {"key": "waiting_customer", "label": "Waiting for the business"}
    if case.automation_mode == "off":
        return {"key": "manual", "label": "Manual review"}
    return {"key": "idle", "label": "Idle"}
