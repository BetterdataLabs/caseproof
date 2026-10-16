"""Tracked requests, the simulated customer inbox, staged replies, reminders and the demo clock.

A request has a stable case-scoped intent and an authorised round; a unique key prevents a second effect,
including after a crash between commit and tool return. Request text comes
from approved templates filled with validated facts. The recipient is the fixed case contact.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import catalog
from .actors import Actor, simulation_actor
from .casework import (
    apply_checks,
    outstanding_requests,
    policy_of,
    questions_of,
    reopen_if_complete,
)
from .config import get_settings
from .errors import Conflict, NotFound, Unsupported
from .evidence import ingest_pdf, ingest_status_update, ingest_written_message, withdraw
from .history import bump, record, utcnow
from .models import Case, DocumentVersion, InfoRequest, Question, Reply, RequestItem
from .policies import POLICY_EVIDENCE_TEMPLATE, settings_for

INTENT = "document-followup"
DEFAULT_TEMPLATE = {
    "TOTAL_MISMATCH": "invoice_correction",
    "REPLACEMENT_REJECTED": "invoice_replacement_clarification",
    "NO_SUPPORTED_INVOICE": "supported_document",
    "NO_INVOICE": "supported_document",
    "RECEIPT_SHORTFALL": "missing_receipt",
    "DISPUTE_RETAINED": "receipt_correction",
}


def allowed_templates(question: Question, authorised_correction: bool) -> list[str]:
    """Approved templates for a question in its current state."""
    if question.state == "resolved":
        return []
    if question.authorised_template:
        return [question.authorised_template]  # a reviewer authorised exactly this follow-up
    if question.reason_code in {"POLICY_ISSUE", "POLICY_EVIDENCE_MISSING"}:
        return ["policy_evidence"]
    if question.requirement_key == "invoice_total":
        if question.reason_code == "REPLACEMENT_REJECTED":
            if (question.metrics or {}).get("rejection_code") in ("REPLACEMENT_SCOPE", "WRONG_ISSUER"):
                return []  # a correction changing other fields or from another issuer goes to a person
            return ["invoice_replacement_clarification", "invoice_correction"]
        if question.reason_code in ("NO_SUPPORTED_INVOICE", "NO_INVOICE"):
            return ["supported_document"]
        if question.reason_code in ("TOTAL_MISMATCH", "PARTY_MISMATCH", "REFERENCE_MISMATCH"):
            return ["invoice_correction"]
        return []
    if question.requirement_key == "delivery_receipts":
        templates = []
        if question.reason_code in ("RECEIPT_SHORTFALL", "RECEIPT_MISMATCH"):
            templates.append("missing_receipt")
        if question.reason_code == "CONDITIONS_NOT_MET":
            return []  # a different correction returns to a reviewer; only a new decision authorises more
        if authorised_correction or question.reason_code == "DISPUTE_RETAINED":
            templates.append("receipt_correction")
        if question.reason_code in ("CUMULATIVE_RECEIPT", "CONFLICTING_DELIVERY_EVENT"):
            templates.append("receipt_basis_clarification")
        return templates
    return []


def new_need_templates(authorised_correction: bool) -> set[str]:
    """Templates that ask for something an outstanding request did not already ask for."""
    needs = {
        "invoice_replacement_clarification",
        "receipt_basis_clarification",
        "receipt_correction_authorised",
        "policy_evidence",
    }
    if authorised_correction:
        needs.add("receipt_correction")
    return needs


def templates_for_snapshot(
    question: Question, authorised_correction: bool, outstanding_templates: set[str]
) -> list[str]:
    """Templates the agent may use now. A question already covered by an outstanding request may only receive a
    request for a genuinely new need, never the same template again."""
    allowed = allowed_templates(question, authorised_correction)
    if outstanding_templates:
        new = new_need_templates(authorised_correction)
        allowed = [t for t in allowed if t in new and t not in outstanding_templates]
    return allowed


def outstanding_templates(session: Session, case_id: uuid.UUID) -> dict[uuid.UUID, set[str]]:
    out: dict[uuid.UUID, set[str]] = {}
    rows = session.execute(
        select(RequestItem.question_id, RequestItem.template_id)
        .join(InfoRequest, InfoRequest.id == RequestItem.request_id)
        .where(
            InfoRequest.case_id == case_id,
            InfoRequest.state == "issued",
            InfoRequest.stop_reached_at.is_(None),
            RequestItem.status.in_(("outstanding", "progress")),
        )
    ).all()
    for question_id, template in rows:
        out.setdefault(question_id, set()).add(template)
    return out


def _fill(
    template_id: str,
    case: Case,
    question: Question,
    all_questions: dict[str, Question],
    conditions: dict[str, Any] | None,
    policy: dict[str, Any],
) -> str:
    template = (
        POLICY_EVIDENCE_TEMPLATE if template_id == "policy_evidence" else policy["templates"][template_id]
    )["text"]
    total_q = all_questions["invoice_total"].metrics or {}
    delivery_q = all_questions["delivery_receipts"].metrics or {}
    m = question.metrics or {}

    def money(value: Any) -> str:
        try:
            return f"SGD {Decimal(str(value)):,.2f}"
        except Exception:
            return str(value)

    values = {
        "invoice_number": case.invoice_reference,
        "seller_name": case.seller["name"],
        "receipt_issuers": " or ".join(p["name"] for p in case.permitted_receipt_issuers),
        "item": delivery_q.get("item") or "the invoiced goods",
        "unit": delivery_q.get("unit") or total_q.get("unit") or "units",
        "outstanding_quantity": delivery_q.get("outstanding_quantity", "the remaining"),
        "known_deliveries": delivery_q.get("known_deliveries", "earlier deliveries"),
        "stated_total": money(total_q.get("stated_total", "")),
        "expected_total": money(total_q.get("expected_total", "")),
        "quantity": total_q.get("quantity", ""),
        "unit_price": money(total_q.get("unit_price", "")),
        "invoice_version": total_q.get("invoice_version", 1),
        "rejection": m.get("rejection", question.detail),
        "document_label": m.get("rejected_label", "the document"),
        "receipt_number": (conditions or {}).get("receipt_number", "the disputed receipt"),
        "receipt_version": (conditions or {}).get("disputed_version", 1),
        "delivery_ref": (conditions or {}).get("delivery_ref", "the disputed delivery"),
        "receipt_label": m.get("receipt_label", "the receipt"),
        "policy_title": question.label,
        "policy_issue": question.detail,
        "policy_criteria": next(
            (r["description"] for r in policy["requirements"] if r["key"] == question.requirement_key), ""
        ),
    }
    return template.format(**values)


def rounds_available(case: Case, session: Session) -> int:
    return (
        settings_for(session, case)["request_rounds"]
        + case.extra_rounds_authorised
        - case.request_rounds_used
    )


def prepare_request(
    session: Session,
    case: Case,
    actor: Actor,
    *,
    items: list[dict[str, Any]],
    authorised_decision_id: uuid.UUID | None = None,
    conditions: dict[str, Any] | None = None,
    created_by: str = "agent",
) -> InfoRequest:
    policy = policy_of(session, case).definition
    questions = questions_of(session, case.id)
    by_id = {str(q.id): q for q in questions.values()}
    if not items:
        raise Unsupported("NO_ITEMS", "A request needs at least one open question.")
    if rounds_available(case, session) <= 0:
        raise Conflict("ROUND_LIMIT", "No request round remains. A person must authorise a further round.")
    from .casework import outstanding_question_ids

    already = outstanding_question_ids(session, case.id)
    resolved_items: list[tuple[Question, str]] = []
    active_keys = {rule["key"] for rule in policy["requirements"]}
    for item in items:
        q = by_id.get(str(item.get("question_id")))
        if q is None or q.requirement_key not in active_keys:
            raise NotFound("QUESTION_NOT_FOUND", "Question is not part of this case's current policy.")
        allowed = allowed_templates(q, authorised_correction=bool(conditions))
        template = item.get("template_id") or (allowed[0] if allowed else None)
        if template not in allowed:
            raise Conflict(
                "TEMPLATE_NOT_ALLOWED",
                f"Template {template} is not approved for '{q.label}' in state {q.reason_code}.",
                allowed=allowed,
            )
        if (
            q.id in already
            and not q.authorised_template
            and (
                template not in new_need_templates(bool(conditions))
                or template in outstanding_templates(session, case.id).get(q.id, set())
            )
        ):
            raise Conflict(
                "ALREADY_REQUESTED",
                f"'{q.label}' is already covered by an outstanding request; wait for the reply.",
            )
        resolved_items.append((q, template))

    round_no = case.request_rounds_used + 1
    existing = session.execute(
        select(InfoRequest).where(
            InfoRequest.case_id == case.id, InfoRequest.intent_key == INTENT, InfoRequest.round == round_no
        )
    ).scalar_one_or_none()
    if existing is not None and existing.state not in ("draft", "proposed"):
        return existing  # replay: the round already exists
    if existing is not None:
        for old in session.execute(
            select(RequestItem).where(RequestItem.request_id == existing.id)
        ).scalars():
            old.status = "discarded"  # drafts are revised, never deleted
        request = existing
    else:
        request = InfoRequest(
            org_id=case.org_id,
            case_id=case.id,
            intent_key=INTENT,
            round=round_no,
            recipient=(
                f"{case.seller['name']} <{case.seller['contact']}>"
                if case.seller.get("contact")
                else case.seller["name"]
            ),
            subject="",
            body="",
            prepared_revision=case.revision,
            created_by=created_by,
        )
        session.add(request)
        session.flush()
    lines = []
    for index, (q, template) in enumerate(resolved_items, start=1):
        text = _fill(template, case, q, questions, conditions, policy)
        session.add(
            RequestItem(
                org_id=case.org_id, request_id=request.id, question_id=q.id, template_id=template, text=text
            )
        )
        lines.append(f"{index}. {text}")
    request.subject = f"Documents needed for invoice {case.invoice_reference} — {case.reference}"
    request.body = (
        f"Dear {case.seller['name']},\n\nTo continue the document review for your financing request on invoice "
        f"{case.invoice_reference}, we need the following:\n\n"
        + "\n\n".join(lines)
        + "\n\nPlease reply through the secure document exchange. Each item is tracked separately, so you can send "
        "documents as they become available.\n\nTrade Operations — Document Review"
    )
    request.prepared_revision = case.revision
    request.authorised_by_decision_id = authorised_decision_id
    request.state = "draft"
    record(
        session,
        case,
        "RequestPrepared",
        actor,
        f"Request round {round_no} prepared with {len(lines)} item(s)",
        payload={"request_id": str(request.id), "items": [t for _, t in resolved_items]},
    )
    return request


def issue_request(
    session: Session, case: Case, actor: Actor, request_id: uuid.UUID, *, shadow: bool = False
) -> tuple[InfoRequest, str]:
    request = session.execute(
        select(InfoRequest)
        .where(InfoRequest.id == request_id, InfoRequest.case_id == case.id)
        .with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise NotFound("REQUEST_NOT_FOUND", "Request is not part of this case.")
    if request.state in ("issued", "answered", "closed"):
        return request, "ALREADY_ISSUED"
    items = (
        session.execute(
            select(RequestItem).where(RequestItem.request_id == request.id, RequestItem.status != "discarded")
        )
        .scalars()
        .all()
    )
    questions = {q.id: q for q in questions_of(session, case.id).values()}
    if any(questions[i.question_id].state == "resolved" for i in items):
        raise Conflict(
            "ITEM_RESOLVED", "An item in this request is already resolved; prepare the request again."
        )
    if request.prepared_revision > case.revision:
        raise Conflict("STALE_REQUEST", "Request was prepared against a different revision.")
    if rounds_available(case, session) <= 0:
        raise Conflict("ROUND_LIMIT", "No request round remains.")
    if shadow:
        request.state = "proposed"
        record(
            session,
            case,
            "ShadowActionProposed",
            actor,
            f"Shadow mode: would issue request round {request.round}",
            payload={"request_id": str(request.id)},
        )
        return request, "SHADOW_PROPOSED"
    now = utcnow()
    request.state = "issued"
    request.issued_at = now
    policy_settings = settings_for(session, case)
    request.reminder_due_at = now + timedelta(hours=policy_settings["reminder_after_hours"])
    request.stop_due_at = request.reminder_due_at + timedelta(
        hours=policy_settings["stop_after_reminder_hours"]
    )
    case.request_rounds_used += 1
    # Earlier outstanding items for the same questions are closed by this newer round.
    for older in outstanding_requests(session, case.id):
        if older.id == request.id:
            continue
        for item in session.execute(select(RequestItem).where(RequestItem.request_id == older.id)).scalars():
            if item.question_id in {i.question_id for i in items} and item.status in (
                "outstanding",
                "progress",
            ):
                item.status = "closed"
        older_items = (
            session.execute(select(RequestItem).where(RequestItem.request_id == older.id)).scalars().all()
        )
        if all(i.status in ("answered", "closed", "discarded") for i in older_items):
            older.state = "closed"
    for item in items:
        q = questions[item.question_id]
        q.authorised_template = None  # the authorised follow-up has now been sent
        if q.state != "waiting_decision":
            q.state = "waiting_evidence"
    try:
        session.flush()
    except IntegrityError as exc:  # pragma: no cover - guarded by the unique intent/round key
        raise Conflict("DUPLICATE_REQUEST", "This request round already exists.") from exc
    record(
        session,
        case,
        "RequestIssued",
        actor,
        f"Request round {request.round} sent to {case.seller['name']} (simulated inbox): {len(items)} item(s)",
        payload={
            "request_id": str(request.id),
            "round": request.round,
            "reminder_due_at": request.reminder_due_at.isoformat(),
        },
    )
    return request, "ISSUED"


# replies


def receive_staged_response(
    session: Session, case: Case, actor: Actor, *, staged_key: str | None, composed_text: str | None
) -> tuple[Reply, bool]:
    """Simulation operator supplies a predefined fictional response (or, in the private evaluation lane, a
    composed message). Returns (reply, created). An exact replay returns the earlier reply with no new work."""
    settings = get_settings()
    policy = policy_of(session, case).definition
    if staged_key:
        try:
            staged = catalog.staged_response(case.scenario_key, staged_key)
        except KeyError as exc:
            raise Unsupported(
                "UNKNOWN_STAGED_RESPONSE", "Only predefined staged responses are accepted."
            ) from exc
        dedupe = f"staged:{staged_key}"
    elif composed_text is not None:
        if not settings.allow_composed_messages:
            raise Unsupported("COMPOSED_DISABLED", "Composed messages are disabled in this environment.")
        text = composed_text.strip()
        if not 3 <= len(text) <= 1200:
            raise Unsupported("MESSAGE_LENGTH", "A composed message must be 3–1,200 characters.")
        staged = {
            "key": None,
            "kind": "written_message",
            "sender": case.seller["key"],
            "attributed_to": case.seller["key"],
            "text": text,
            "label": "Composed written message",
        }
        dedupe = "composed:" + hashlib.sha256(text.encode()).hexdigest()[:32]
    else:
        raise Unsupported("NO_RESPONSE", "Choose a staged response.")

    existing = session.execute(
        select(Reply).where(Reply.case_id == case.id, Reply.dedupe_key == dedupe)
    ).scalar_one_or_none()
    if existing is not None:
        record(
            session,
            case,
            "DuplicateSuppressed",
            actor,
            f"Exact replay ignored: {existing.summary}",
            payload={"reply_id": str(existing.id)},
        )
        return existing, False

    sender_name = catalog.parties()[staged["sender"]]["name"]
    customer = simulation_actor(case.org_id, sender_name)
    requests = outstanding_requests(session, case.id)
    latest = max(requests, key=lambda r: r.round) if requests else None
    reply = Reply(
        org_id=case.org_id,
        case_id=case.id,
        request_id=latest.id if latest else None,
        kind=staged["kind"],
        staged_key=staged.get("key"),
        dedupe_key=dedupe,
        summary=staged["label"],
        sender=sender_name,
        case_revision=case.revision,
    )
    session.add(reply)
    session.flush()
    if latest:
        latest.last_reply_at = utcnow()

    versions: list[DocumentVersion] = []
    reason = staged["label"]
    if staged["kind"] == "document":
        doc = staged["document"]
        versions.append(
            ingest_pdf(
                session,
                case,
                customer,
                role=doc["role"],
                data=catalog.fixture_bytes(doc),
                declared_issuer=doc["declared_issuer"],
                received_via="reply",
                fixture_key=doc["key"],
                reply_id=reply.id,
                policy=policy,
            )
        )
    elif staged["kind"] == "written_message":
        versions.append(
            ingest_written_message(
                session,
                case,
                customer,
                text=staged["text"],
                attributed_to=staged.get("attributed_to", staged["sender"]),
                received_via="reply",
                reply_id=reply.id,
                fixture_key=staged.get("key"),
                policy=policy,
            )
        )
    elif staged["kind"] == "status_update":
        version = ingest_status_update(
            session, case, customer, fields=staged["fields"], reply_id=reply.id, policy=policy
        )
        versions.append(version)
        _record_progress(session, case, staged["fields"])
    elif staged["kind"] == "withdrawal":
        target = staged["withdraw"]
        version = withdraw(
            session,
            case,
            customer,
            role=target["role"],
            number=target["number"],
            reason=staged.get("note", ""),
        )
        if version is None:
            raise Conflict("NOTHING_TO_WITHDRAW", "That document is not active on this case.")
        versions.append(version)
    reply.version_ids = [str(v.id) for v in versions]
    record(
        session,
        case,
        "ReplyReceived",
        customer,
        f"Reply received from {sender_name}: {staged['label']}",
        payload={"reply_id": str(reply.id), "kind": staged["kind"], "versions": reply.version_ids},
    )
    bump(case)
    reopen_if_complete(session, case, actor, f"new input: {reason}")
    apply_checks(session, case, actor, resolve=False)
    return reply, True


def _record_progress(session: Session, case: Case, fields: dict[str, Any]) -> None:
    """A dispatch update is progress on the receipt item, never receipt evidence."""
    delivery = questions_of(session, case.id)["delivery_receipts"]
    for item in session.execute(
        select(RequestItem)
        .join(InfoRequest, InfoRequest.id == RequestItem.request_id)
        .where(
            InfoRequest.case_id == case.id,
            InfoRequest.state == "issued",
            RequestItem.question_id == delivery.id,
            RequestItem.status.in_(("outstanding", "progress")),
        )
    ).scalars():
        item.status = "progress"
        item.progress_note = (
            f"{fields.get('quantity')} {fields.get('unit')} for {fields.get('delivery_ref')} reported "
            f"{fields.get('status')}: {fields.get('note', '')}"
        ).strip()


# timers


def advance_demo_clock(session: Session, case: Case, actor: Actor, hours: int) -> int:
    """Simulation only: move this case's pending policy timers forward by `hours`."""
    if not 1 <= hours <= 24 * 14:
        raise Unsupported("CLOCK_RANGE", "Advance between 1 hour and 14 days.")
    delta = timedelta(hours=hours)
    moved = 0
    for request in outstanding_requests(session, case.id):
        if request.reminder_due_at and not request.reminder_sent_at:
            request.reminder_due_at -= delta
            moved += 1
        if request.stop_due_at and not request.stop_reached_at:
            request.stop_due_at -= delta
            moved += 1
    case.clock_offset_s += hours * 3600
    record(
        session,
        case,
        "DemoClockAdvanced",
        actor,
        f"Demo clock advanced {hours} h ({moved} timer(s) moved)",
        payload={"hours": hours},
    )
    return moved


def due_timer_effects(session: Session, case: Case) -> list[str]:
    """Policy timers: one reminder per outstanding request, then a human stop condition. No model calls."""
    from .actors import system_actor
    from .tasks import open_task

    actor = system_actor(case.org_id)
    now = utcnow()
    effects = []
    for request in outstanding_requests(session, case.id):
        items = (
            session.execute(
                select(RequestItem).where(
                    RequestItem.request_id == request.id, RequestItem.status.in_(("outstanding", "progress"))
                )
            )
            .scalars()
            .all()
        )
        if not items:
            continue
        if request.reminder_sent_at is None and request.reminder_due_at and request.reminder_due_at <= now:
            request.reminder_sent_at = now
            request.stop_due_at = max(request.stop_due_at or now, now)
            if request.stop_due_at <= now:
                request.stop_due_at = now + timedelta(
                    hours=settings_for(session, case)["stop_after_reminder_hours"]
                )
            record(
                session,
                case,
                "ReminderSent",
                actor,
                f"Reminder sent for request round {request.round}: {len(items)} item(s) still outstanding",
                payload={"request_id": str(request.id)},
            )
            effects.append("reminder")
        elif (
            request.reminder_sent_at
            and request.stop_reached_at is None
            and request.stop_due_at
            and request.stop_due_at <= now
        ):
            request.stop_reached_at = now
            questions = {q.id: q for q in questions_of(session, case.id).values()}
            keys = sorted({questions[i.question_id].requirement_key for i in items})
            open_task(
                session,
                case,
                actor,
                kind="no_response",
                requirement_keys=keys,
                source_version_ids=[],
                observation_ids=[],
                passages=[],
                title=f"No reply to request round {request.round}",
                question=(
                    f"{case.seller['name']} has not supplied the requested evidence after the reminder. "
                    f"Authorise a further request round, or keep the case on hold?"
                ),
                why_stopped="The policy allows one reminder per request. The stop point has passed with items outstanding.",
                proposed_action="Authorise one further round asking for the same outstanding items.",
                dedupe_key=f"no_response:{request.id}",
            )
            effects.append("stop")
    if effects:
        bump(case)
        if "stop" in effects:
            for q in questions_of(session, case.id).values():
                if q.state == "waiting_evidence":
                    q.state = "waiting_decision"
    return effects


def pending_timer_cases(session: Session) -> list[tuple[uuid.UUID, uuid.UUID]]:
    now = utcnow()
    rows = session.execute(
        select(InfoRequest.org_id, InfoRequest.case_id)
        .where(
            InfoRequest.state == "issued",
            (
                (InfoRequest.reminder_sent_at.is_(None) & (InfoRequest.reminder_due_at <= now))
                | (
                    InfoRequest.reminder_sent_at.is_not(None)
                    & InfoRequest.stop_reached_at.is_(None)
                    & (InfoRequest.stop_due_at <= now)
                )
            ),
        )
        .distinct()
    ).all()
    return [(r[0], r[1]) for r in rows]
