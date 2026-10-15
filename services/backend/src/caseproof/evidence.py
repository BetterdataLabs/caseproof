"""Evidence lifecycle: immutable originals, strict parsing, verified facts, source authority and replacement.

States: received → validating → ready | rejected; later withdrawn | superseded.
A file hash identifies a copy, not a delivery. A newer file alone never replaces the active version.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import catalog
from .actors import Actor
from .checks import VersionView
from .errors import Unsupported
from .history import record, utcnow
from .models import Case, Document, DocumentVersion, Fact
from .pdfdocs import PARSER_VERSION, parse_document
from .storage import object_store

ROLE_LABEL = {
    "invoice": "Invoice",
    "delivery_receipt": "Delivery receipt",
    "written_message": "Written message",
    "status_update": "Status update",
}
COMPARED_FIELDS = {
    "invoice": [
        "invoice_number",
        "seller",
        "seller_uen",
        "buyer",
        "item",
        "quantity",
        "unit",
        "unit_price",
        "tax",
        "other_charges",
        "total_amount",
        "issue_date",
        "payment_terms",
    ],
    "delivery_receipt": [
        "receipt_number",
        "delivery_ref",
        "invoice_ref",
        "issued_by",
        "supplier",
        "item",
        "quantity",
        "unit",
        "received_at",
        "basis",
        "condition",
    ],
}


def _party_name(key: str | None) -> str:
    if not key:
        return ""
    return catalog.parties().get(key, {}).get("name", key)


def _next_sequence(session: Session, case: Case) -> int:
    current = session.execute(
        select(func.coalesce(func.max(DocumentVersion.sequence), 0)).where(DocumentVersion.case_id == case.id)
    ).scalar_one()
    return int(current) + 1


def _admission(session: Session, case: Case, size: int, policy: dict[str, Any]) -> None:
    limits = policy["limits"]
    count = session.execute(select(func.count()).where(DocumentVersion.case_id == case.id)).scalar_one()
    if count >= limits["max_sources_per_case"]:
        raise Unsupported(
            "SOURCE_LIMIT", f"A case accepts at most {limits['max_sources_per_case']} source versions."
        )
    if size > limits["max_bytes_per_original"]:
        raise Unsupported(
            "FILE_TOO_LARGE",
            f"The original exceeds this policy’s {limits['max_bytes_per_original'] / 1048576:g} MiB file limit.",
        )


def facts_of(session: Session, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    out: dict[uuid.UUID, dict[str, str]] = {vid: {} for vid in version_ids}
    if not version_ids:
        return out
    for fact in session.execute(
        select(Fact).where(Fact.version_id.in_(version_ids), Fact.verified.is_(True))
    ).scalars():
        out[fact.version_id][fact.field] = fact.value
    return out


def _get_document(session: Session, case: Case, role: str, number: str, title: str) -> Document:
    doc = session.execute(
        select(Document).where(Document.case_id == case.id, Document.role == role, Document.number == number)
    ).scalar_one_or_none()
    if doc is None:
        doc = Document(org_id=case.org_id, case_id=case.id, role=role, number=number, title=title)
        session.add(doc)
        session.flush()
    return doc


def ingest_pdf(
    session: Session,
    case: Case,
    actor: Actor,
    *,
    role: str,
    data: bytes,
    declared_issuer: str,
    received_via: str,
    fixture_key: str | None = None,
    reply_id: uuid.UUID | None = None,
    policy: dict[str, Any],
) -> DocumentVersion:
    """Register one original. Caller holds the case lock and bumps the revision once per command."""
    _admission(session, case, len(data), policy)
    sha = hashlib.sha256(data).hexdigest()
    key = f"orgs/{case.org_id}/cases/{case.id}/originals/{sha}.pdf"
    generation = object_store().put_immutable(key, data)  # written and verified before registration

    sequence = _next_sequence(session, case)
    parsed = parse_document(data, policy["limits"]["max_pages_per_document"])
    number = (
        parsed.value("invoice_number") if role == "invoice" else parsed.value("receipt_number")
    ) or f"UNREAD-{sequence}"
    doc = _get_document(session, case, role, number, f"{ROLE_LABEL[role]} {number}")

    version = DocumentVersion(
        org_id=case.org_id,
        case_id=case.id,
        document_id=doc.id,
        label=f"S{sequence}",
        sequence=sequence,
        source_role=role,
        declared_issuer=_party_name(declared_issuer),
        state="validating",
        object_key=key,
        object_generation=generation,
        sha256=sha,
        size_bytes=len(data),
        mime="application/pdf",
        page_count=parsed.page_count,
        text_content=parsed.text[:20000],
        received_via=received_via,
        fixture_key=fixture_key,
        reply_id=reply_id,
        parser_version=PARSER_VERSION,
        received_revision=case.revision,
    )
    session.add(version)
    session.flush()

    # Facts are verified against the extracted text: the quote must occur and must end with the value.
    for fact in parsed.facts:
        verified = fact.quote in parsed.text and fact.quote.endswith(fact.value)
        session.add(
            Fact(
                org_id=case.org_id,
                case_id=case.id,
                version_id=version.id,
                field=fact.field,
                value=fact.value,
                quote=fact.quote,
                page=fact.page,
                verified=verified,
            )
        )
    session.flush()

    duplicate = (
        session.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.case_id == case.id,
                DocumentVersion.sha256 == sha,
                DocumentVersion.id != version.id,
                DocumentVersion.duplicate_of_id.is_(None),
            )
            .order_by(DocumentVersion.sequence)
        )
        .scalars()
        .first()
    )

    if not parsed.ok:
        _reject(version, parsed.reject_code or "UNSUPPORTED", parsed.reject_detail)
    elif parsed.doc_type != role:
        _reject(
            version,
            "ROLE_MISMATCH",
            f"The document is a {parsed.doc_type}, not a {ROLE_LABEL[role].lower()}.",
        )
    elif duplicate is not None:
        version.state = (
            duplicate.state if duplicate.state in ("ready", "superseded", "withdrawn") else "ready"
        )
        version.duplicate_of_id = duplicate.id
        version.version_no = duplicate.version_no
        version.business_event_ref = duplicate.business_event_ref
        version.coverage = "processed"
        version.reject_detail = f"Identical copy of {duplicate.label}; it is retained but counted once."
    else:
        _validate_and_activate(session, case, doc, version, parsed.facts, declared_issuer, policy)

    record(
        session,
        case,
        "EvidenceReceived",
        actor,
        f"{version.label} received: {ROLE_LABEL[role].lower()} {number}"
        + (f" (copy of {duplicate.label})" if duplicate else ""),
        payload={
            "version_id": str(version.id),
            "label": version.label,
            "role": role,
            "sha256": sha,
            "state": version.state,
        },
    )
    if version.state == "rejected":
        record(
            session,
            case,
            "EvidenceRejected",
            actor,
            f"{version.label} not accepted: {version.reject_detail}",
            payload={"version_id": str(version.id), "code": version.reject_code},
        )
    elif version.duplicate_of_id is None:
        record(
            session,
            case,
            "EvidenceReady",
            actor,
            f"{version.label} validated: {len(parsed.facts)} facts verified",
            payload={"version_id": str(version.id), "active": version.is_active},
        )
    return version


def _reject(version: DocumentVersion, code: str, detail: str) -> None:
    version.state = "rejected"
    version.reject_code = code
    version.reject_detail = detail
    version.coverage = "blocking"
    version.is_active = False


def _validate_and_activate(
    session: Session,
    case: Case,
    doc: Document,
    version: DocumentVersion,
    facts: list[Any],
    declared_issuer: str,
    policy: dict[str, Any],
) -> None:
    values = {f.field: f.value for f in facts}
    role = version.source_role
    version.version_no = int(values["version"])
    version.replaces_version_no = (
        int(values["replaces_version"]) if values["replaces_version"].isdigit() else None
    )
    if role == "delivery_receipt":
        version.business_event_ref = values.get("delivery_ref")

    # Source authority: the declared source role (catalog assumption) and the printed issuer must both be permitted.
    if role == "invoice":
        permitted = [case.seller["name"]]
        printed = values.get("seller")
    else:
        permitted = [p["name"] for p in case.permitted_receipt_issuers]
        printed = values.get("issued_by")
    declared = _party_name(declared_issuer)
    if printed not in permitted or declared not in permitted or declared != printed:
        _reject(
            version,
            "WRONG_ISSUER",
            f"Issued by '{printed}', which is not a permitted source for this {ROLE_LABEL[role].lower()}.",
        )
        return

    previous = (
        session.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.id != version.id,
                DocumentVersion.duplicate_of_id.is_(None),
            )
            .order_by(DocumentVersion.sequence)
        )
        .scalars()
        .all()
    )
    active = next((p for p in previous if p.is_active), None)
    rule = policy["replacement_rules"][role]

    if active is None:
        if any(p.state == "ready" and (p.version_no or 0) >= version.version_no for p in previous):
            _reject(version, "VERSION_CONFLICT", "A version with the same or a later number already exists.")
            return
        _activate(doc, version, previous)
        return

    if version.version_no <= (active.version_no or 0):
        _reject(
            version,
            "VERSION_CONFLICT",
            f"Version {version.version_no} does not follow active version {active.version_no} of {doc.number}.",
        )
        return
    if rule["requires_explicit_supersession"] and version.replaces_version_no != active.version_no:
        _reject(
            version,
            "REPLACEMENT_NOT_EXPLICIT",
            f"{doc.number} v{version.version_no} does not state that it replaces v{active.version_no}; both versions "
            f"are preserved and the original stays active.",
        )
        return
    active_facts = facts_of(session, [active.id])[active.id]
    if active.parser_version == "gemini-pdf/1":
        # Reader defaults are workflow metadata, deliberately excluded from verified source facts.
        for name, default in {
            "tax": "none",
            "other_charges": "none",
            "basis": "this delivery",
            "condition": "",
            "seller_uen": "",
            "issue_date": "",
            "payment_terms": "",
        }.items():
            active_facts.setdefault(name, default)
    changed = [f for f in COMPARED_FIELDS[role] if active_facts.get(f) != values.get(f)]
    outside = [f for f in changed if f not in rule["may_change"]]
    if outside:
        _reject(
            version,
            "REPLACEMENT_SCOPE",
            f"{doc.number} v{version.version_no} also changes {', '.join(f.replace('_', ' ') for f in outside)}, "
            f"which a replacement may not change automatically.",
        )
        return
    active.is_active = False
    active.state = "superseded"
    _activate(doc, version, previous)


def _activate(doc: Document, version: DocumentVersion, previous: list[DocumentVersion]) -> None:
    version.state = "ready"
    version.is_active = True
    version.coverage = "processed"
    doc.active_version_id = version.id
    for p in previous:
        if (
            p.state == "rejected"
            and p.coverage == "blocking"
            and (p.version_no or 0) <= (version.version_no or 0)
        ):
            p.coverage = "not_required"  # a later accepted version addresses the earlier unusable one


def ingest_written_message(
    session: Session,
    case: Case,
    actor: Actor,
    *,
    text: str,
    attributed_to: str,
    received_via: str,
    reply_id: uuid.UUID | None,
    fixture_key: str | None,
    policy: dict[str, Any],
) -> DocumentVersion:
    _admission(session, case, len(text.encode()), policy)
    sequence = _next_sequence(session, case)
    count = session.execute(
        select(func.count()).where(Document.case_id == case.id, Document.role == "written_message")
    ).scalar_one()
    number = f"MSG-{count + 1}"
    doc = _get_document(session, case, "written_message", number, f"Written message {number}")
    data = text.encode()
    version = DocumentVersion(
        org_id=case.org_id,
        case_id=case.id,
        document_id=doc.id,
        label=f"S{sequence}",
        sequence=sequence,
        source_role="written_message",
        declared_issuer="",
        attributed_to=_party_name(attributed_to),
        state="ready",
        is_active=True,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        mime="text/plain",
        text_content=text,
        coverage="needs_review",
        received_via=received_via,
        reply_id=reply_id,
        fixture_key=fixture_key,
        version_no=1,
        received_revision=case.revision,
    )
    session.add(version)
    session.flush()
    doc.active_version_id = version.id
    record(
        session,
        case,
        "EvidenceReceived",
        actor,
        f"{version.label} received: written message {number} attributed to {version.attributed_to or 'unknown sender'}",
        payload={"version_id": str(version.id), "label": version.label, "role": "written_message"},
    )
    return version


def ingest_status_update(
    session: Session,
    case: Case,
    actor: Actor,
    *,
    fields: dict[str, Any],
    reply_id: uuid.UUID,
    policy: dict[str, Any],
) -> DocumentVersion:
    sequence = _next_sequence(session, case)
    count = session.execute(
        select(func.count()).where(Document.case_id == case.id, Document.role == "status_update")
    ).scalar_one()
    number = f"STATUS-{count + 1}"
    doc = _get_document(session, case, "status_update", number, f"Status update {number}")
    text = (
        f"Delivery {fields.get('delivery_ref')}: {fields.get('quantity')} {fields.get('unit')} — "
        f"{fields.get('status')}. {fields.get('note', '')}"
    ).strip()
    version = DocumentVersion(
        org_id=case.org_id,
        case_id=case.id,
        document_id=doc.id,
        label=f"S{sequence}",
        sequence=sequence,
        source_role="status_update",
        state="ready",
        is_active=True,
        structured=fields,
        text_content=text,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        mime="application/json",
        coverage="processed",
        received_via="reply",
        reply_id=reply_id,
        version_no=1,
        business_event_ref=fields.get("delivery_ref"),
        received_revision=case.revision,
    )
    session.add(version)
    session.flush()
    doc.active_version_id = version.id
    record(
        session,
        case,
        "EvidenceReceived",
        actor,
        f"{version.label} received: structured status update — {text}",
        payload={
            "version_id": str(version.id),
            "label": version.label,
            "role": "status_update",
            "fields": fields,
        },
    )
    return version


def withdraw(
    session: Session, case: Case, actor: Actor, *, role: str, number: str, reason: str
) -> DocumentVersion | None:
    doc = session.execute(
        select(Document).where(Document.case_id == case.id, Document.role == role, Document.number == number)
    ).scalar_one_or_none()
    if doc is None or doc.active_version_id is None:
        return None
    version = session.get(DocumentVersion, doc.active_version_id)
    assert version is not None
    version.state = "withdrawn"
    version.is_active = False
    version.withdrawn_at = utcnow()
    version.coverage = "processed"
    doc.active_version_id = None
    for copy in session.execute(
        select(DocumentVersion).where(DocumentVersion.duplicate_of_id == version.id)
    ).scalars():
        copy.state = "withdrawn"
    record(
        session,
        case,
        "EvidenceWithdrawn",
        actor,
        f"{version.label} ({number}) withdrawn",
        reason=reason,
        payload={"version_id": str(version.id)},
    )
    return version


def version_views(session: Session, case_id: uuid.UUID) -> list[VersionView]:
    rows = session.execute(
        select(DocumentVersion, Document.number)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(DocumentVersion.case_id == case_id)
        .order_by(DocumentVersion.sequence)
    ).all()
    facts = facts_of(session, [v.id for v, _ in rows])
    return [
        VersionView(
            id=str(v.id),
            label=v.label,
            role=v.source_role,
            number=number,
            version_no=v.version_no,
            replaces_version_no=v.replaces_version_no,
            state=v.state,
            is_active=v.is_active,
            duplicate_of=str(v.duplicate_of_id) if v.duplicate_of_id else None,
            coverage=v.coverage,
            facts=facts.get(v.id, {}),
            reject_code=v.reject_code,
            reject_detail=v.reject_detail,
        )
        for v, number in rows
    ]
