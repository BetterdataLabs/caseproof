"""Vendor contact access and the customer-facing conversation on the same bank case."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .actors import ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_VENDOR, Actor
from .errors import Conflict, Forbidden, NotFound, Unsupported
from .history import bump, record
from .models import Case, Document, DocumentVersion, InfoRequest, Membership, Organisation, Reply, User


def require_access(case: Case, actor: Actor) -> None:
    if case.org_id != actor.org_id or case.vendor_contact_id != actor.user_id:
        raise NotFound("CASE_NOT_FOUND", "Submission not found.")


def set_contact(session: Session, case: Case, actor: Actor, user_id: str | None) -> None:
    if not actor.has(ROLE_REVIEWER, ROLE_SUPERVISOR):
        raise Forbidden("BANK_REVIEWER_REQUIRED", "A bank reviewer chooses the vendor contact.")
    if case.lifecycle == "archived":
        raise Conflict("CASE_ARCHIVED", "Archived cases cannot change vendor contact.")
    contact = None
    if user_id:
        try:
            contact_id = uuid.UUID(user_id)
        except ValueError as exc:
            raise Unsupported("INVALID_VENDOR_CONTACT", "Choose an active vendor contact.") from exc
        member = session.execute(
            select(Membership).where(
                Membership.org_id == case.org_id,
                Membership.user_id == contact_id,
                Membership.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if member is None or set(member.roles) != {ROLE_VENDOR}:
            raise Unsupported("INVALID_VENDOR_CONTACT", "Choose an active vendor in this organisation.")
        contact = session.get(User, contact_id)
    selected = contact.id if contact else None
    if case.vendor_contact_id == selected:
        return
    previous = case.vendor_contact_id
    case.vendor_contact_id = selected
    bump(case)
    record(
        session,
        case,
        "VendorContactChanged",
        actor,
        f"Vendor portal contact: {contact.display_name if contact else 'not assigned'}",
        payload={
            "previous_user_id": str(previous) if previous else None,
            "user_id": str(selected) if selected else None,
        },
    )
    # Fence an in-flight worker and preserve its obligation to continue after a contact change.
    if case.execution in {"queued", "running"}:
        from .jobs import enqueue_agent

        enqueue_agent(session, case, "Continuation", "Vendor contact changed")


def reviewer_for(session: Session, actor: Actor):
    reviewer = session.execute(
        select(User.id)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.org_id == actor.org_id,
            Membership.revoked_at.is_(None),
            Membership.roles.overlap([ROLE_REVIEWER, ROLE_SUPERVISOR]),
        )
        .order_by((User.subject == "dev:alex").desc(), User.display_name)
        .limit(1)
    ).scalar_one_or_none()
    if reviewer is None:
        raise Unsupported("NO_REVIEWER", "The bank needs an active reviewer before accepting submissions.")
    return reviewer


def summary(case: Case) -> dict:
    if case.lifecycle == "archived":
        status, label, help_ = "closed", "Closed", "The bank has closed this submission."
    elif case.lifecycle == "complete":
        status, label, help_ = (
            "complete",
            "Review complete",
            "Your document review is complete. The bank handles the financing decision separately.",
        )
    elif case.execution in {"queued", "running"}:
        status, label, help_ = (
            "processing",
            "Reviewing documents",
            "Your information has been received. We will show any requests here.",
        )
    elif case.execution == "waiting_evidence":
        status, label, help_ = (
            "reply_needed",
            "Reply needed",
            "Read the bank's request below, then reply or attach the requested documents.",
        )
    else:
        status, label, help_ = (
            "bank_review",
            "With the bank",
            "The bank is reviewing your submission. Any request for more information will appear here.",
        )
    return {
        "id": str(case.id),
        "reference": case.reference,
        "title": case.title,
        "invoice": case.invoice_reference,
        "seller": case.seller.get("name", ""),
        "buyer": case.buyer.get("name", ""),
        "revision": case.revision,
        "research_status": (case.credit_research or {}).get("status"),
        "status": status,
        "status_label": label,
        "next_step": help_,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "can_reply": case.lifecycle != "archived",
        "can_upload": case.lifecycle != "archived" and case.automation_mode == "autonomous",
    }


def detail(session: Session, actor: Actor, case: Case) -> dict:
    require_access(case, actor)
    rows = session.execute(
        select(DocumentVersion, Document)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(DocumentVersion.case_id == case.id)
        .order_by(DocumentVersion.sequence)
    ).all()
    bank = session.get(Organisation, case.org_id)
    documents = {
        str(v.id): {
            "id": str(v.id),
            "name": (v.structured or {}).get("filename") or doc.title,
            "number": doc.number,
            "role": v.source_role,
            "version": v.version_no,
            "state": v.state,
            "active": v.is_active,
        }
        for v, doc in rows
        if v.mime == "application/pdf" and v.object_key
    }
    versions = {str(v.id): v for v, _ in rows}
    initial = [v for v, _ in rows if v.reply_id is None]
    creator = session.get(User, case.created_by) if case.created_by else None
    shared_case = case.created_by != actor.user_id
    messages = [
        {
            "id": "submission",
            "direction": "incoming" if shared_case else "outgoing",
            "subject": "Documents added to the case" if shared_case else "Documents submitted for review",
            "sender": (creator.display_name if creator else bank.short_name),
            "recipient": actor.name if shared_case else bank.short_name,
            "created_at": case.created_at.isoformat(),
            "body": "\n\n".join(
                v.text_content for v in initial if v.source_role == "written_message" and v.text_content
            )
            or (
                "These documents are already on the case. Read the bank's requests below and reply with the requested information."
                if shared_case
                else "Please review the attached invoice and delivery evidence."
            ),
            "attachments": [documents[str(v.id)] for v in initial if str(v.id) in documents],
        }
    ]
    requests = session.execute(
        select(InfoRequest)
        .where(
            InfoRequest.case_id == case.id,
            InfoRequest.issued_at.is_not(None),
        )
        .order_by(InfoRequest.issued_at)
    ).scalars()
    for request in requests:
        entry = {
            "id": str(request.id),
            "direction": "incoming",
            "subject": request.subject,
            "sender": bank.short_name,
            "recipient": request.recipient,
            "created_at": request.issued_at.isoformat(),
            "body": request.body,
            "attachments": [],
        }
        messages.append(entry)
        if request.reminder_sent_at:
            messages.append(
                {
                    **entry,
                    "id": f"reminder:{request.id}",
                    "subject": f"Reminder: {request.subject}",
                    "created_at": request.reminder_sent_at.isoformat(),
                }
            )
    for reply in session.execute(
        select(Reply).where(Reply.case_id == case.id).order_by(Reply.created_at)
    ).scalars():
        messages.append(
            {
                "id": str(reply.id),
                "direction": "outgoing",
                "subject": reply.summary,
                "sender": reply.sender,
                "recipient": bank.short_name,
                "created_at": reply.created_at.isoformat(),
                "body": "\n\n".join(
                    versions[v].text_content or ""
                    for v in reply.version_ids
                    if v in versions and versions[v].source_role == "written_message"
                )
                or reply.summary,
                "attachments": [documents[v] for v in reply.version_ids if v in documents],
            }
        )
    return {
        "case": summary(case),
        "bank": bank.short_name,
        "documents": list(documents.values()),
        "messages": sorted(messages, key=lambda item: item["created_at"]),
    }
