"""Human tasks and scoped decisions.

A task records the exact question, affected items, source versions and allowed decisions. There is no
general approval and no bypass for invalid numbers. Task assignment (claim) is separate from decision
authority; submission requires the current case revision and the source versions the person reviewed.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .actors import ROLE_REVIEWER, ROLE_SUPERVISOR, Actor
from .casework import apply_checks, claims_of, policy_of, questions_of
from .config import get_settings
from .document_checks import VISUAL_DECISIONS
from .errors import Conflict, Forbidden, NotFound, StaleRevision, Unsupported
from .history import bump, lock_case, record, utcnow
from .jobs import enqueue_agent, record_pause
from .models import Case, Decision, DocumentVersion, HumanTask, MaterialClaim
from .policy_checks import REVIEW_DECISIONS, review_input

DECISION_LABELS = {
    "accept_policy_review": "Record a supported policy interpretation",
    "exclude_rejected_document": "Exclude this rejected document from the review",
    "accept_document_appearance": "Record appearance review and continue",
    "record_interpretation": "Record a source-backed interpretation",
    "mark_irrelevant": "Mark as not relevant to the checklist",
    "retain_dispute_request_evidence": "Retain the dispute and request specific evidence",
    "keep_on_hold": "Keep the case on hold",
    "authorise_request": "Authorise a further request for corrected evidence",
    "authorise_extra_round": "Authorise one further request round",
    "resume_automation": "Resume automation",
    "grant_extension": "Grant a bounded budget extension",
}
SUPERVISOR_ONLY = {"grant_extension"}
AUTHORISED_TEMPLATE = {
    "REPLACEMENT_REJECTED": "invoice_replacement_clarification",
    "TOTAL_MISMATCH": "invoice_correction",
    "CONDITIONS_NOT_MET": "receipt_correction",
    "DISPUTE_RETAINED": "receipt_correction",
    "CUMULATIVE_RECEIPT": "receipt_basis_clarification",
    "CONFLICTING_DELIVERY_EVENT": "receipt_basis_clarification",
    "RECEIPT_SHORTFALL": "missing_receipt",
    "RECEIPT_MISMATCH": "missing_receipt",
    "NO_SUPPORTED_INVOICE": "supported_document",
}
NEEDS_REASON = set(DECISION_LABELS)


def open_task(
    session: Session,
    case: Case,
    actor: Actor,
    *,
    kind: str,
    requirement_keys: list[str],
    source_version_ids: list[str],
    observation_ids: list[str],
    passages: list[dict[str, Any]],
    title: str,
    question: str,
    why_stopped: str,
    proposed_action: str,
    dedupe_key: str | None = None,
    required_role: str = ROLE_REVIEWER,
) -> tuple[HumanTask, bool]:
    policy = policy_of(session, case).definition
    allowed = (
        REVIEW_DECISIONS
        if kind == "policy_review"
        else VISUAL_DECISIONS
        if kind == "document_review"
        else ["exclude_rejected_document", "keep_on_hold"]
        if kind == "document_rejection"
        else policy["task_decisions"].get(kind)
    )
    if allowed is None:
        raise Unsupported("UNKNOWN_TASK_KIND", f"Task kind {kind} is not defined by the policy.")
    known = {
        str(v.id)
        for v in session.execute(select(DocumentVersion).where(DocumentVersion.case_id == case.id)).scalars()
    }
    for vid in source_version_ids:
        if vid not in known:
            raise Forbidden("SOURCE_OUT_OF_SCOPE", "A referenced source is not part of this case.")
    valid_keys = set(questions_of(session, case.id))
    requirement_keys = [k for k in requirement_keys if k in valid_keys]
    key = dedupe_key or f"{kind}:{','.join(sorted(source_version_ids)) or ','.join(sorted(requirement_keys))}"
    existing = session.execute(
        select(HumanTask).where(
            HumanTask.case_id == case.id,
            HumanTask.dedupe_key == key,
            HumanTask.state.in_(("pending", "claimed")),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    task = HumanTask(
        org_id=case.org_id,
        case_id=case.id,
        kind=kind,
        title=title[:300],
        question=question,
        why_stopped=why_stopped,
        proposed_action=proposed_action,
        requirement_keys=requirement_keys,
        source_version_ids=source_version_ids,
        observation_ids=observation_ids,
        passages=passages,
        allowed_decisions=allowed,
        required_role=ROLE_SUPERVISOR if kind == "budget_exhausted" else required_role,
        opened_by=actor.type,
        created_revision=case.revision,
        dedupe_key=key,
    )
    session.add(task)
    session.flush()
    for q in questions_of(session, case.id).values():
        if q.requirement_key not in requirement_keys:
            continue
        if q.state == "resolved" and kind in ("dispute", "evidence_problem"):
            q.resolved_at = None
            q.resolved_revision = None
            q.resolved_by = None
            record(
                session,
                case,
                "QuestionReopened",
                actor,
                f"Reopened: {q.label}",
                reason=f"Disputed: {title}",
                payload={"requirement": q.requirement_key},
            )
        if q.state != "resolved":
            q.state = "waiting_decision"
    for vid in source_version_ids:
        version = session.get(DocumentVersion, uuid.UUID(vid))
        if version is not None and version.coverage == "pending":
            version.coverage = "needs_review"
    record(
        session,
        case,
        "HumanTaskOpened",
        actor,
        f"Decision needed: {task.title}",
        reason=why_stopped,
        payload={"task_id": str(task.id), "kind": kind, "sources": source_version_ids},
    )
    return task, True


def claim(session: Session, task_id: uuid.UUID, actor: Actor) -> HumanTask:
    task = session.execute(
        select(HumanTask).where(HumanTask.id == task_id).with_for_update()
    ).scalar_one_or_none()
    if task is None:
        raise NotFound("TASK_NOT_FOUND", "Task not found.")
    _authorise(task, actor, None)
    if task.state not in ("pending", "claimed"):
        raise Conflict("TASK_CLOSED", "This task has already been decided.")
    now = utcnow()
    if (
        task.state == "claimed"
        and task.claimed_by != actor.user_id
        and task.claim_expires_at
        and task.claim_expires_at > now
    ):
        raise Conflict(
            "TASK_CLAIMED", "Another reviewer is working on this task.", claimed_by=str(task.claimed_by)
        )
    task.state = "claimed"
    task.claimed_by = actor.user_id
    task.claim_expires_at = now + timedelta(minutes=get_settings().claim_minutes)
    case = session.get(Case, task.case_id)
    record(
        session,
        case,
        "TaskClaimed",
        actor,
        f"{actor.name} is reviewing: {task.title}",
        payload={"task_id": str(task.id)},
    )
    return task


def release(session: Session, task_id: uuid.UUID, actor: Actor) -> HumanTask:
    task = session.execute(
        select(HumanTask).where(HumanTask.id == task_id).with_for_update()
    ).scalar_one_or_none()
    if task is None:
        raise NotFound("TASK_NOT_FOUND", "Task not found.")
    if task.state == "claimed" and task.claimed_by == actor.user_id:
        task.state = "pending"
        task.claimed_by = None
        task.claim_expires_at = None
    return task


def _authorise(task: HumanTask, actor: Actor, decision_type: str | None) -> None:
    if not actor.has(ROLE_REVIEWER, ROLE_SUPERVISOR):
        raise Forbidden("ROLE_REQUIRED", "Only reviewers and supervisors can work on decision tasks.")
    if task.required_role == ROLE_SUPERVISOR and not actor.has(ROLE_SUPERVISOR):
        raise Forbidden("SUPERVISOR_REQUIRED", "This decision needs an operations supervisor.")
    if decision_type in SUPERVISOR_ONLY and not actor.has(ROLE_SUPERVISOR):
        raise Forbidden("SUPERVISOR_REQUIRED", "Only a supervisor can grant an extension.")


def decide(
    session: Session,
    task_id: uuid.UUID,
    actor: Actor,
    *,
    decision_type: str,
    reason: str,
    expected_revision: int,
    covered_version_ids: list[str],
    params: dict[str, Any],
) -> Decision:
    task = session.execute(
        select(HumanTask).where(HumanTask.id == task_id).with_for_update()
    ).scalar_one_or_none()
    if task is None:
        raise NotFound("TASK_NOT_FOUND", "Task not found.")
    case = lock_case(session, task.case_id)
    _authorise(task, actor, decision_type)
    if task.state in ("decided", "superseded"):
        raise Conflict("TASK_CLOSED", "This task has already been decided.")
    now = utcnow()
    if (
        task.state == "claimed"
        and task.claimed_by != actor.user_id
        and task.claim_expires_at
        and task.claim_expires_at > now
    ):
        raise Conflict("TASK_CLAIMED", "Another reviewer holds this task.")
    if case.revision != expected_revision:
        raise StaleRevision(
            "STALE_REVISION",
            "The case changed while you were reviewing. Check the updated evidence, then resubmit.",
            current_revision=case.revision,
        )
    if sorted(covered_version_ids) != sorted(task.source_version_ids):
        raise StaleRevision(
            "SOURCES_CHANGED", "The sources covered by this task have changed. Review them again."
        )
    if decision_type not in task.allowed_decisions:
        raise Conflict(
            "DECISION_NOT_ALLOWED",
            "That decision is not available for this task.",
            allowed=task.allowed_decisions,
        )
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise Unsupported("REASON_REQUIRED", "Record a short reason for the decision.")

    decision = Decision(
        org_id=case.org_id,
        case_id=case.id,
        task_id=task.id,
        actor_id=actor.user_id,
        decision_type=decision_type,
        reason=reason,
        conditions={},
        covered_version_ids=covered_version_ids,
        case_revision=case.revision,
    )
    session.add(decision)
    session.flush()
    covered = [session.get(DocumentVersion, uuid.UUID(v)) for v in covered_version_ids]
    wake = True
    summary = f"{actor.name}: {DECISION_LABELS[decision_type]}"

    if task.kind == "policy_review" and decision_type in {"accept_policy_review", "authorise_request"}:
        from copy import deepcopy

        report = deepcopy(case.policy_review or {})
        if report.get("fingerprint") != review_input(session, case)["fingerprint"]:
            raise Conflict(
                "POLICY_EVIDENCE_CHANGED",
                "The policy or documents changed. Review the current assessment first.",
            )
        for key in task.requirement_keys:
            finding = report["results"][key]
            if decision_type == "accept_policy_review":
                if not covered or not any(v and v.is_active and v.state == "ready" for v in covered):
                    raise Unsupported(
                        "EVIDENCE_REQUIRED", "A policy interpretation requires a current, accepted document."
                    )
                finding["disposition"] = {
                    "decision_id": str(decision.id),
                    "reviewed_by": actor.name,
                    "reason": reason,
                    "reviewed_at": now.isoformat(),
                }
            else:
                finding["request_authorised"] = True
                questions_of(session, case.id)[key].authorised_template = "policy_evidence"
        case.policy_review = report
        if decision_type == "authorise_request":
            case.extra_rounds_authorised += 1
            _close_outstanding(session, case, task.requirement_keys)
        if case.paused_reason == "ON_HOLD":
            case.execution, case.paused_reason = "idle", None
    elif decision_type == "exclude_rejected_document":
        from .casework import compute_checks

        if (
            task.kind != "document_rejection"
            or not covered
            or any(not version or version.state != "rejected" or version.is_active for version in covered)
        ):
            raise Unsupported(
                "WRONG_SOURCE", "This action only excludes the rejected documents cited by this task."
            )
        if any(result.result != "pass" for result in compute_checks(session, case).values()):
            raise Conflict(
                "CHECKS_INCOMPLETE", "The remaining evidence must satisfy every checklist question first."
            )
        for version in covered:
            version.coverage = "not_required"
            version.covered_by_decision_id = decision.id
    elif decision_type == "accept_document_appearance":
        if task.kind != "document_review":
            raise Unsupported("WRONG_TASK", "This decision only covers document appearance findings.")
        for version in covered:
            if version and (version.visual_review or {}).get("status") == "review_required":
                version.visual_review = {
                    **version.visual_review,
                    "status": "reviewed",
                    "decision_id": str(decision.id),
                    "reviewed_by": actor.name,
                    "reviewed_at": now.isoformat(),
                    "review_reason": reason,
                }
        if case.paused_reason == "ON_HOLD":
            case.execution, case.paused_reason = "idle", None
    elif decision_type in ("record_interpretation", "mark_irrelevant"):
        if decision_type == "record_interpretation":
            interpretation = (params.get("interpretation") or "").strip()
            if len(interpretation) < 5:
                raise Unsupported("INTERPRETATION_REQUIRED", "Record the interpretation the sources support.")
            decision.conditions = {"interpretation": interpretation}
        _cover(covered, decision.id)
    elif decision_type == "retain_dispute_request_evidence":
        conditions = _dispute_conditions(session, case, params)
        decision.conditions = conditions
        for claim_row in claims_of(session, case.id):
            if claim_row.status == "retained" and claim_row.requirement_key == "delivery_receipts":
                claim_row.status = "superseded"
        source = (
            covered[0] if covered and covered[0] and covered[0].source_role == "written_message" else None
        )
        session.add(
            MaterialClaim(
                org_id=case.org_id,
                case_id=case.id,
                requirement_key="delivery_receipts",
                source_version_id=(source.id if source else uuid.UUID(task.source_version_ids[0])),
                decision_id=decision.id,
                statement=(
                    f"Delivery {conditions['delivery_ref']} had {conditions['claimed_quantity']} received, "
                    f"disputing {conditions['receipt_number']} v{conditions['disputed_version']}"
                ),
                conditions=conditions,
            )
        )
        case.extra_rounds_authorised += 1
        _close_outstanding(session, case, ["delivery_receipts"])
        _cover(covered, decision.id)
        summary += (
            f" — corrected {conditions['receipt_number']} must state {conditions['claimed_quantity']} for "
            f"{conditions['delivery_ref']}; remaining quantity needs distinct receipts"
        )
    elif decision_type in ("authorise_request", "authorise_extra_round"):
        case.extra_rounds_authorised += 1
        _close_outstanding(session, case, task.requirement_keys)
        for q in questions_of(session, case.id).values():
            if q.requirement_key in task.requirement_keys and q.state != "resolved":
                q.authorised_template = AUTHORISED_TEMPLATE.get(q.reason_code) or q.authorised_template
    elif decision_type == "keep_on_hold":
        wake = False
        record_pause(session, case, actor, "ON_HOLD", f"On hold by {actor.name}: {reason}")
    elif decision_type == "resume_automation":
        case.execution = "idle"
        case.paused_reason = None
    elif decision_type == "grant_extension":
        extra_wakeups = int(params.get("extra_wakeups", 4))
        extra_budget = Decimal(str(params.get("extra_budget_usd", "0.25")))
        if not (1 <= extra_wakeups <= 6) or not (Decimal("0") <= extra_budget <= Decimal("0.50")):
            raise Unsupported("EXTENSION_RANGE", "An extension is bounded: up to 6 wake-ups and USD 0.50.")
        case.wakeup_extension += extra_wakeups
        case.budget_usd = Decimal(case.budget_usd) + extra_budget
        decision.conditions = {"extra_wakeups": extra_wakeups, "extra_budget_usd": str(extra_budget)}
        case.execution = "idle"
        case.paused_reason = None
    task.state = "decided"
    task.decided_at = now
    bump(case)
    record(
        session,
        case,
        "HumanDecisionRecorded",
        actor,
        summary,
        reason=reason,
        payload={
            "task_id": str(task.id),
            "decision_id": str(decision.id),
            "decision": decision_type,
            "conditions": decision.conditions,
            "covered": covered_version_ids,
        },
    )
    apply_checks(session, case, actor, resolve=False)
    if wake:
        trigger = (
            "RecoveryRequested"
            if decision_type in ("resume_automation", "grant_extension")
            else "HumanDecisionRecorded"
        )
        enqueue_agent(session, case, trigger, f"{DECISION_LABELS[decision_type]}: {reason}")
    from .casework import settle_execution

    settle_execution(session, case)
    return decision


def _close_outstanding(session: Session, case: Case, requirement_keys: list[str]) -> None:
    """A decision authorising new evidence supersedes what earlier requests asked for on those questions."""
    from .models import InfoRequest, RequestItem

    questions = questions_of(session, case.id)
    ids = {questions[k].id for k in requirement_keys if k in questions}
    for item in session.execute(
        select(RequestItem)
        .join(InfoRequest, InfoRequest.id == RequestItem.request_id)
        .where(
            InfoRequest.case_id == case.id,
            InfoRequest.state == "issued",
            RequestItem.status.in_(("outstanding", "progress")),
        )
    ).scalars():
        if item.question_id in ids:
            item.status = "closed"
    for request in session.execute(
        select(InfoRequest).where(InfoRequest.case_id == case.id, InfoRequest.state == "issued")
    ).scalars():
        items = (
            session.execute(select(RequestItem).where(RequestItem.request_id == request.id)).scalars().all()
        )
        if all(i.status in ("answered", "closed", "discarded") for i in items):
            request.state = "closed"


def _cover(versions: list[DocumentVersion | None], decision_id: uuid.UUID) -> None:
    for version in versions:
        if version is not None and version.coverage in ("needs_review", "pending", "blocking"):
            version.coverage = "reviewed"
            version.covered_by_decision_id = decision_id


def _dispute_conditions(session: Session, case: Case, params: dict[str, Any]) -> dict[str, Any]:
    receipt_number = str(params.get("receipt_number") or "").strip()
    delivery_ref = str(params.get("delivery_ref") or "").strip()
    try:
        claimed = Decimal(str(params.get("claimed_quantity")))
    except Exception as exc:
        raise Unsupported("CONDITIONS_REQUIRED", "Record the disputed quantity as a number.") from exc
    if not receipt_number or not delivery_ref or claimed <= 0 or claimed != claimed.to_integral_value():
        raise Unsupported("CONDITIONS_REQUIRED", "Record the receipt, delivery and the disputed quantity.")
    from .models import Document

    doc = session.execute(
        select(Document).where(
            Document.case_id == case.id,
            Document.role == "delivery_receipt",
            Document.number == receipt_number,
        )
    ).scalar_one_or_none()
    if doc is None or doc.active_version_id is None:
        raise Unsupported("RECEIPT_NOT_FOUND", f"Receipt {receipt_number} is not active on this case.")
    active = session.get(DocumentVersion, doc.active_version_id)
    return {
        "receipt_number": receipt_number,
        "delivery_ref": delivery_ref,
        "claimed_quantity": str(claimed),
        "disputed_version": active.version_no if active else 1,
        "requires_distinct_receipts_for_remainder": True,
        "requires_explicit_supersession": True,
    }
