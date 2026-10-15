"""Read models for the operations workspace. Role-specific; no model credentials or object paths exposed."""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .actors import ROLE_ADMIN, ROLE_REVIEWER, ROLE_SIMULATION, ROLE_SUPERVISOR, Actor
from .casework import case_primary_status, claims_of, completion_blockers, open_tasks, policy_of
from .config import get_settings
from .credit_research import public_report
from .document_checks import public_config
from .evidence import ROLE_LABEL
from .models import (
    AgentAction,
    AgentRun,
    AuditEvent,
    Case,
    Decision,
    Document,
    DocumentVersion,
    Export,
    Fact,
    HumanTask,
    InfoRequest,
    Observation,
    PolicyVersion,
    Question,
    Reply,
    RequestItem,
    User,
)
from .policies import settings_for
from .tasks import DECISION_LABELS


def iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def money(value: Any) -> str:
    return str(Decimal(value or 0).quantize(Decimal("0.0001")))


def user_names(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.display_name for u in session.execute(select(User).where(User.id.in_(ids))).scalars()}


def etag_for(case: Case) -> str:
    raw = f"{case.id}:{case.revision}:{case.execution}:{case.updated_at.isoformat()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def case_summary(
    case: Case, tasks: list[HumanTask], questions: list[Question], names: dict[uuid.UUID, str]
) -> dict[str, Any]:
    status = case_primary_status(case, tasks)
    open_q = [q for q in questions if q.state != "resolved"]
    return {
        "id": str(case.id),
        "reference": case.reference,
        "title": case.title,
        "revision": case.revision,
        "lifecycle": case.lifecycle,
        "execution": case.execution,
        "automation_mode": case.automation_mode,
        "paused_reason": case.paused_reason,
        "status": status,
        "next_action": case.next_action,
        "next_event_at": iso(case.next_event_at),
        "seller": case.seller["name"],
        "buyer": case.buyer["name"],
        "invoice_reference": case.invoice_reference,
        "facility_reference": case.facility_reference,
        "assigned_to": {"id": str(case.assigned_to), "name": names.get(case.assigned_to, "")}
        if case.assigned_to
        else None,
        "open_questions": len(open_q),
        "total_questions": len(questions),
        "question_states": [
            {"key": q.requirement_key, "state": q.state, "result": q.check_result} for q in questions
        ],
        "pending_tasks": len(tasks),
        "created_at": iso(case.created_at),
        "updated_at": iso(case.updated_at),
        "completed_at": iso(case.completed_at),
        "scenario_key": case.scenario_key,
        "etag": etag_for(case),
    }


def list_cases(
    session: Session,
    actor: Actor,
    *,
    view: str,
    assigned: str | None,
    query: str | None,
    cursor: str | None,
    limit: int = 50,
) -> dict[str, Any]:
    stmt = select(Case).where(Case.org_id == actor.org_id, Case.lifecycle != "archived")
    if assigned == "me" and actor.user_id:
        stmt = stmt.where(Case.assigned_to == actor.user_id)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            (Case.reference.ilike(like))
            | (Case.title.ilike(like))
            | (Case.invoice_reference.ilike(like))
            | (Case.seller["name"].astext.ilike(like))
        )
    cases = session.execute(stmt.order_by(Case.updated_at.desc(), Case.id.desc())).scalars().all()
    ids = [c.id for c in cases]
    tasks_by_case: dict[uuid.UUID, list[HumanTask]] = {i: [] for i in ids}
    questions_by_case: dict[uuid.UUID, list[Question]] = {i: [] for i in ids}
    if ids:
        for t in session.execute(
            select(HumanTask).where(HumanTask.case_id.in_(ids), HumanTask.state.in_(("pending", "claimed")))
        ).scalars():
            tasks_by_case[t.case_id].append(t)
        for q in session.execute(
            select(Question).where(Question.case_id.in_(ids)).order_by(Question.requirement_key)
        ).scalars():
            questions_by_case[q.case_id].append(q)
    names = user_names(session, {c.assigned_to for c in cases})
    policy_keys = {
        p.id: {r["key"] for r in p.definition["requirements"]}
        for p in session.execute(
            select(PolicyVersion).where(PolicyVersion.id.in_({c.policy_id for c in cases}))
        ).scalars()
    }
    rows = [
        case_summary(
            c,
            tasks_by_case[c.id],
            [q for q in questions_by_case[c.id] if q.requirement_key in policy_keys[c.policy_id]],
            names,
        )
        for c in cases
    ]
    counts: dict[str, int] = {"all": len(rows)}
    for r in rows:
        counts[r["status"]["key"]] = counts.get(r["status"]["key"], 0) + 1
    if view and view != "all":
        rows = [r for r in rows if r["status"]["key"] == view]
    start = int(cursor) if cursor and cursor.isdigit() else 0
    page = rows[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(rows) else None
    return {"items": page, "counts": counts, "next_cursor": next_cursor}


def _facts(session: Session, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict[str, Any]]]:
    out: dict[uuid.UUID, list[dict[str, Any]]] = {v: [] for v in version_ids}
    if version_ids:
        for f in session.execute(select(Fact).where(Fact.version_id.in_(version_ids))).scalars():
            if not f.quote and not f.verified:
                continue  # reader defaults are source metadata, not quoted business facts
            out[f.version_id].append(
                {"field": f.field, "value": f.value, "quote": f.quote, "page": f.page, "verified": f.verified}
            )
    return out


def version_json(
    v: DocumentVersion, facts: list[dict[str, Any]], labels: dict[uuid.UUID, str]
) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "label": v.label,
        "role": v.source_role,
        "role_label": ROLE_LABEL[v.source_role],
        "version_no": v.version_no,
        "replaces_version_no": v.replaces_version_no,
        "state": v.state,
        "is_active": v.is_active,
        "coverage": v.coverage,
        "reject_code": v.reject_code,
        "reject_detail": v.reject_detail,
        "duplicate_of": labels.get(v.duplicate_of_id) if v.duplicate_of_id else None,
        "business_event_ref": v.business_event_ref,
        "sha256": v.sha256,
        "size_bytes": v.size_bytes,
        "page_count": v.page_count,
        "mime": v.mime,
        "received_via": v.received_via,
        "created_at": iso(v.created_at),
        "declared_issuer": v.declared_issuer,
        "attributed_to": v.attributed_to,
        "structured": v.structured,
        "visual_review": v.visual_review,
        "text": v.text_content if v.source_role in ("written_message", "status_update") else None,
        "facts": facts,
        "has_preview": v.mime == "application/pdf",
        "covered_by_decision_id": str(v.covered_by_decision_id) if v.covered_by_decision_id else None,
    }


def case_detail(session: Session, actor: Actor, case: Case) -> dict[str, Any]:
    tasks_open = open_tasks(session, case.id)
    questions = (
        session.execute(
            select(Question).where(Question.case_id == case.id).order_by(Question.requirement_key.desc())
        )
        .scalars()
        .all()
    )
    all_tasks = (
        session.execute(
            select(HumanTask).where(HumanTask.case_id == case.id).order_by(HumanTask.created_at.desc())
        )
        .scalars()
        .all()
    )
    decisions = {
        d.task_id: d for d in session.execute(select(Decision).where(Decision.case_id == case.id)).scalars()
    }
    names = user_names(
        session,
        {case.assigned_to, case.vendor_contact_id}
        | {t.claimed_by for t in all_tasks}
        | {d.actor_id for d in decisions.values()},
    )
    policy = policy_of(session, case)
    requirements = {r["key"]: r for r in policy.definition["requirements"]}

    versions = (
        session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.case_id == case.id)
            .order_by(DocumentVersion.sequence)
        )
        .scalars()
        .all()
    )
    labels = {v.id: v.label for v in versions}
    facts = _facts(session, [v.id for v in versions])
    documents = []
    for doc in session.execute(
        select(Document).where(Document.case_id == case.id).order_by(Document.created_at)
    ).scalars():
        doc_versions = [version_json(v, facts[v.id], labels) for v in versions if v.document_id == doc.id]
        documents.append(
            {
                "id": str(doc.id),
                "role": doc.role,
                "role_label": ROLE_LABEL[doc.role],
                "number": doc.number,
                "title": doc.title,
                "active_version_id": str(doc.active_version_id) if doc.active_version_id else None,
                "versions": doc_versions,
            }
        )

    q_by_id = {q.id: q for q in questions}
    requests = []
    for r in session.execute(
        select(InfoRequest).where(InfoRequest.case_id == case.id).order_by(InfoRequest.round)
    ).scalars():
        items = (
            session.execute(
                select(RequestItem).where(RequestItem.request_id == r.id, RequestItem.status != "discarded")
            )
            .scalars()
            .all()
        )
        requests.append(
            {
                "id": str(r.id),
                "round": r.round,
                "state": r.state,
                "subject": r.subject,
                "body": r.body,
                "recipient": r.recipient,
                "issued_at": iso(r.issued_at),
                "reminder_due_at": iso(r.reminder_due_at),
                "reminder_sent_at": iso(r.reminder_sent_at),
                "stop_due_at": iso(r.stop_due_at),
                "stop_reached_at": iso(r.stop_reached_at),
                "created_by": r.created_by,
                "created_at": iso(r.created_at),
                "items": [
                    {
                        "id": str(i.id),
                        "question_key": q_by_id[i.question_id].requirement_key,
                        "question_label": q_by_id[i.question_id].label,
                        "template_id": i.template_id,
                        "text": i.text,
                        "status": i.status,
                        "progress_note": i.progress_note,
                    }
                    for i in items
                ],
            }
        )
    replies = [
        {
            "id": str(r.id),
            "kind": r.kind,
            "summary": r.summary,
            "sender": r.sender,
            "created_at": iso(r.created_at),
            "request_id": str(r.request_id) if r.request_id else None,
            "versions": [labels.get(uuid.UUID(v), v) for v in r.version_ids],
        }
        for r in session.execute(
            select(Reply).where(Reply.case_id == case.id).order_by(Reply.created_at)
        ).scalars()
    ]

    observations = {
        str(o.id): o
        for o in session.execute(select(Observation).where(Observation.case_id == case.id)).scalars()
    }
    tasks_json = []
    for t in all_tasks:
        d = decisions.get(t.id)
        tasks_json.append(
            {
                "id": str(t.id),
                "kind": t.kind,
                "state": t.state,
                "title": t.title,
                "question": t.question,
                "why_stopped": t.why_stopped,
                "proposed_action": t.proposed_action,
                "requirement_keys": t.requirement_keys,
                "source_version_ids": t.source_version_ids,
                "source_labels": [labels.get(uuid.UUID(v), v) for v in t.source_version_ids],
                "passages": t.passages,
                "required_role": t.required_role,
                "opened_by": t.opened_by,
                "allowed_decisions": [
                    {"type": a, "label": DECISION_LABELS.get(a, a)} for a in t.allowed_decisions
                ],
                "claimed_by": {"id": str(t.claimed_by), "name": names.get(t.claimed_by, "")}
                if t.claimed_by
                else None,
                "claim_expires_at": iso(t.claim_expires_at),
                "created_at": iso(t.created_at),
                "decided_at": iso(t.decided_at),
                "observations": [
                    _observation_json(observations[o], labels) for o in t.observation_ids if o in observations
                ],
                "decision": {
                    "type": d.decision_type,
                    "label": DECISION_LABELS.get(d.decision_type, d.decision_type),
                    "reason": d.reason,
                    "conditions": d.conditions,
                    "actor": names.get(d.actor_id, ""),
                    "created_at": iso(d.created_at),
                }
                if d
                else None,
            }
        )

    runs = []
    run_rows = (
        session.execute(
            select(AgentRun).where(AgentRun.case_id == case.id).order_by(AgentRun.started_at.desc()).limit(30)
        )
        .scalars()
        .all()
    )
    actions_by_run: dict[uuid.UUID, list[dict[str, Any]]] = {r.id: [] for r in run_rows}
    if run_rows:
        for a in session.execute(
            select(AgentAction).where(AgentAction.run_id.in_(list(actions_by_run))).order_by(AgentAction.seq)
        ).scalars():
            actions_by_run[a.run_id].append(
                {
                    "seq": a.seq,
                    "tool": a.tool,
                    "args": a.args,
                    "result_code": a.result_code,
                    "result_summary": a.result_summary,
                    "reason": a.reason,
                    "shadow": a.shadow,
                    "duration_ms": a.duration_ms,
                    "created_at": iso(a.created_at),
                }
            )
    for r in run_rows:
        runs.append(
            {
                "id": str(r.id),
                "trigger": r.trigger,
                "mode": r.mode,
                "controller": r.controller,
                "model": r.model,
                "outcome": r.outcome,
                "stop_reason": r.stop_reason,
                "summary": r.summary,
                "model_calls": r.model_calls,
                "tool_calls": r.tool_calls,
                "retries": r.retries,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": money(r.cost_usd),
                "input_revision": r.input_revision,
                "final_revision": r.final_revision,
                "started_at": iso(r.started_at),
                "ended_at": iso(r.ended_at),
                "actions": actions_by_run[r.id],
            }
        )

    exports = [
        {
            "id": str(e.id),
            "export_ref": e.export_ref,
            "state": e.state,
            "case_revision": e.case_revision,
            "policy_label": e.policy_label,
            "created_at": iso(e.created_at),
            "ready_at": iso(e.ready_at),
            "superseded_reason": e.superseded_reason,
            "is_current": e.id == case.current_export_id,
            "pdf_sha256": e.pdf_sha256,
        }
        for e in session.execute(
            select(Export).where(Export.case_id == case.id).order_by(Export.created_at.desc())
        ).scalars()
    ]

    timeline = [
        audit_json(e)
        for e in session.execute(
            select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id.desc()).limit(80)
        ).scalars()
    ]

    claims = [
        {
            "id": str(c.id),
            "requirement_key": c.requirement_key,
            "statement": c.statement,
            "status": c.status,
            "conditions": c.conditions,
            "source": labels.get(c.source_version_id),
            "created_at": iso(c.created_at),
        }
        for c in claims_of(session, case.id)
    ]
    settings = get_settings()
    summary = case_summary(
        case, tasks_open, [q for q in questions if q.requirement_key in requirements], names
    )
    policy_settings = settings_for(session, case)
    blockers = completion_blockers(session, case) if case.lifecycle != "complete" else []
    return {
        "case": {
            **summary,
            "policy": {
                "id": str(policy.id),
                "key": policy.key,
                "version": policy.version,
                "name": policy.name,
                "limits": policy_settings,
            },
            "seller_detail": case.seller,
            "buyer_detail": case.buyer,
            "receipt_issuers": [p["name"] for p in case.permitted_receipt_issuers],
            "document_checks": public_config(case.document_checks),
            "credit_research": public_report(case.credit_research),
            "vendor_contact": {
                "id": str(case.vendor_contact_id),
                "name": names.get(case.vendor_contact_id, "Vendor contact"),
            }
            if case.vendor_contact_id
            else None,
            "budget": {
                "wakeups_used": case.wakeups_used,
                "wakeups_max": policy_settings["automatic_wakeups_per_case"] + case.wakeup_extension,
                "rounds_used": case.request_rounds_used,
                "rounds_max": policy_settings["request_rounds"] + case.extra_rounds_authorised,
                "cost_reserved_usd": money(case.cost_reserved_usd),
                "cost_actual_usd": money(case.cost_actual_usd),
                "budget_usd": money(case.budget_usd),
            },
            "clock_offset_hours": case.clock_offset_s // 3600,
            "expires_at": iso(case.expires_at),
            "current_export_id": str(case.current_export_id) if case.current_export_id else None,
        },
        "questions": [
            {
                "id": str(q.id),
                "key": q.requirement_key,
                "label": q.label,
                "criteria": requirements[q.requirement_key]["description"],
                "state": q.state,
                "check_result": q.check_result,
                "reason_code": q.reason_code,
                "detail": q.detail,
                "metrics": q.metrics,
                "evidence": [labels.get(uuid.UUID(v), v) for v in (q.evidence_refs or [])],
                "resolved_at": iso(q.resolved_at),
                "resolved_by": q.resolved_by,
                "resolved_revision": q.resolved_revision,
            }
            for q in sorted(
                questions,
                key=lambda q: (
                    list(requirements).index(q.requirement_key)
                    if q.requirement_key in requirements
                    else len(requirements)
                ),
            )
            if q.requirement_key in requirements
        ],
        "documents": documents,
        "requests": requests,
        "replies": replies,
        "tasks": tasks_json,
        "claims": claims,
        "runs": runs,
        "exports": exports,
        "timeline": timeline,
        "blockers": blockers,
        "permissions": {
            "decide": actor.has(ROLE_REVIEWER, ROLE_SUPERVISOR),
            "supervise": actor.has(ROLE_SUPERVISOR),
            "simulate": actor.has(ROLE_SIMULATION) and settings.demo_mode and case.scenario_key != "uploaded",
            "add_input": actor.has(ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_SIMULATION)
            and case.lifecycle != "archived",
            "administer": actor.has(ROLE_ADMIN),
            "compose_messages": settings.allow_composed_messages,
        },
    }


def _observation_json(o: Observation, labels: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "relation": o.relation,
        "affected_requirement": o.affected_requirement,
        "summary": o.summary,
        "payload": o.payload,
        "model": o.model,
        "valid": o.valid,
        "subject": labels.get(o.subject_version_id),
        "compared": [labels.get(uuid.UUID(v), v) for v in o.compared_version_ids],
        "created_at": iso(o.created_at),
    }


def audit_json(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "event_id": str(e.event_id),
        "type": e.event_type,
        "actor_type": e.actor_type,
        "actor": e.actor_name,
        "summary": e.summary,
        "reason": e.reason,
        "revision": e.case_revision,
        "created_at": iso(e.created_at),
        "payload": e.payload,
    }


def task_inbox(session: Session, actor: Actor) -> list[dict[str, Any]]:
    rows = session.execute(
        select(HumanTask, Case)
        .join(Case, Case.id == HumanTask.case_id)
        .where(HumanTask.state.in_(("pending", "claimed")))
        .order_by(HumanTask.created_at)
    ).all()
    names = user_names(session, {t.claimed_by for t, _ in rows})
    return [
        {
            "id": str(t.id),
            "kind": t.kind,
            "state": t.state,
            "title": t.title,
            "question": t.question,
            "case": {"id": str(c.id), "reference": c.reference, "title": c.title, "seller": c.seller["name"]},
            "required_role": t.required_role,
            "created_at": iso(t.created_at),
            "claimed_by": names.get(t.claimed_by) if t.claimed_by else None,
        }
        for t, c in rows
    ]
