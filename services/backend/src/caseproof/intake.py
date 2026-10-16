"""User supplied originals and replies. Reading happens in the bounded worker, after upload."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .actors import Actor
from .casework import apply_checks, next_reference, policy_of, reopen_if_complete
from .credit_research import ResearchOptions
from .credit_research import configure as configure_research
from .document_checks import configure_checks, pending_review
from .document_content import EXTENSIONS, identify_format
from .errors import Conflict, Unsupported
from .evidence import _admission, _get_document, _next_sequence, ingest_written_message
from .history import bump, record, utcnow
from .models import Case, DocumentVersion, InfoRequest, PolicyVersion, Question, Reply
from .policies import definition_for
from .storage import object_store

MAX_UPLOAD_BYTES = 21 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 5


@dataclass
class Upload:
    name: str
    role: str
    data: bytes
    replaces: str | None = None

    def fingerprint(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "replaces": self.replaces,
        }


def register_upload(
    session: Session, case: Case, actor: Actor, upload: Upload, reply_id: uuid.UUID | None = None
) -> DocumentVersion:
    policy = policy_of(session, case).definition
    sha = hashlib.sha256(upload.data).hexdigest()
    previous = (
        session.execute(
            select(DocumentVersion).where(
                DocumentVersion.case_id == case.id,
                DocumentVersion.sha256 == sha,
                DocumentVersion.source_role == upload.role,
            )
        )
        .scalars()
        .first()
    )
    if previous:
        record(
            session,
            case,
            "DuplicateSuppressed",
            actor,
            f"{upload.name}: already received as {previous.label}",
        )
        return previous
    _admission(session, case, len(upload.data), policy)
    if upload.replaces:
        target = session.get(DocumentVersion, uuid.UUID(upload.replaces))
        if (
            not target
            or target.case_id != case.id
            or target.source_role != upload.role
            or not target.is_active
        ):
            raise Conflict(
                "REPLACEMENT_CHANGED",
                "The document to replace is no longer active. Refresh and select it again.",
            )
    sequence = _next_sequence(session, case)
    mime = identify_format(upload.data, upload.name)
    key = f"orgs/{case.org_id}/cases/{case.id}/originals/{sha}.{EXTENSIONS[mime]}"
    generation = object_store().put_immutable(key, upload.data)
    doc = _get_document(session, case, upload.role, f"UPLOAD-{sequence}", upload.name)
    version = DocumentVersion(
        org_id=case.org_id,
        case_id=case.id,
        document_id=doc.id,
        label=f"S{sequence}",
        sequence=sequence,
        source_role=upload.role,
        state="received",
        coverage="pending",
        received_via="upload",
        sha256=sha,
        size_bytes=len(upload.data),
        mime=mime,
        object_key=key,
        object_generation=generation,
        reply_id=reply_id,
        received_revision=case.revision,
        structured={"filename": upload.name, "replaces": upload.replaces},
        parser_version="upload/1",
        visual_review=pending_review(case.document_checks, upload.role)
        if mime == "application/pdf"
        else None,
    )
    session.add(version)
    session.flush()
    record(
        session,
        case,
        "EvidenceReceived",
        actor,
        f"{version.label} uploaded: {upload.name}",
        payload={"version_id": str(version.id), **upload.fingerprint()},
    )
    return version


def create_uploaded_case(
    session: Session,
    actor: Actor,
    uploads: list[Upload],
    message: str,
    sender: str = "",
    *,
    tampering: bool = False,
    references: list[Upload] | None = None,
    research: ResearchOptions | None = None,
) -> Case:
    policy = (
        session.execute(
            select(PolicyVersion)
            .where(PolicyVersion.status == "published")
            .order_by(PolicyVersion.version.desc())
        )
        .scalars()
        .first()
    )
    if not policy:
        raise Unsupported("POLICY_NOT_FOUND", "No published review checklist is available.")
    case = Case(
        org_id=actor.org_id,
        reference=next_reference(session, actor.org_id),
        title=uploads[0].name[:200],
        policy_id=policy.id,
        scenario_key="uploaded",
        seller={"key": "uploaded-seller", "name": "Reading invoice…"},
        buyer={"key": "uploaded-buyer", "name": "Reading invoice…"},
        permitted_receipt_issuers=[],
        invoice_reference="",
        assigned_to=actor.user_id,
        automation_mode="autonomous",
        budget_usd=Decimal(str(definition_for(policy)["limits"]["case_budget_usd"])),
        created_by=actor.user_id,
        vendor_contact_id=actor.user_id if actor.workspace == "vendor" else None,
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
    record(
        session,
        case,
        "CaseCreated",
        actor,
        f"Case {case.reference} created from uploaded documents",
        payload={"source": "upload", "policy": str(policy.id)},
    )
    if tampering or references:
        configure_checks(session, case, actor, tampering, references or [])
    if research:
        configure_research(case, actor, session, research)
    for upload in uploads:
        register_upload(session, case, actor, upload)
    if message:
        ingest_written_message(
            session,
            case,
            actor,
            text=message,
            attributed_to=sender or actor.name,
            received_via="upload",
            reply_id=None,
            fixture_key=None,
            policy=policy.definition,
        )
    bump(case)
    return case


def add_input(
    session: Session, case: Case, actor: Actor, uploads: list[Upload], message: str, sender: str
) -> tuple[Reply, bool]:
    if case.lifecycle == "archived":
        raise Conflict("CASE_ARCHIVED", "Archived cases cannot receive new documents.")
    if uploads and case.automation_mode != "autonomous":
        raise Conflict("AUTOMATION_REQUIRED", "Turn on autonomous mode to read uploaded documents.")
    dedupe = (
        "input:"
        + hashlib.sha256(
            json.dumps(
                {
                    "files": [u.fingerprint() for u in uploads],
                    "message": message,
                    "sender": sender or actor.name,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )
    previous = session.execute(
        select(Reply).where(Reply.case_id == case.id, Reply.dedupe_key == dedupe)
    ).scalar_one_or_none()
    if previous:
        return previous, False
    if (
        uploads
        and not message
        and all(
            session.execute(
                select(DocumentVersion.id).where(
                    DocumentVersion.case_id == case.id,
                    DocumentVersion.source_role == u.role,
                    DocumentVersion.sha256 == hashlib.sha256(u.data).hexdigest(),
                )
            ).first()
            for u in uploads
        )
    ):
        raise Conflict(
            "ALREADY_RECEIVED",
            "These documents are already on this case. Add a changed document or a written reply.",
        )
    latest = (
        session.execute(
            select(InfoRequest)
            .where(InfoRequest.case_id == case.id, InfoRequest.state == "issued")
            .order_by(InfoRequest.round.desc())
        )
        .scalars()
        .first()
    )
    reply = Reply(
        org_id=case.org_id,
        case_id=case.id,
        request_id=latest.id if latest else None,
        kind="document" if uploads else "written_message",
        dedupe_key=dedupe,
        summary=(f"{len(uploads)} document(s)" + (" and a written reply" if message else ""))
        if uploads
        else "Written reply",
        sender=sender or actor.name,
        case_revision=case.revision,
    )
    session.add(reply)
    session.flush()
    versions = [register_upload(session, case, actor, u, reply.id) for u in uploads]
    if message:
        versions.append(
            ingest_written_message(
                session,
                case,
                actor,
                text=message,
                attributed_to=sender or actor.name,
                received_via="upload",
                reply_id=reply.id,
                fixture_key=None,
                policy=policy_of(session, case).definition,
            )
        )
    reply.version_ids = [str(v.id) for v in versions]
    if latest:
        latest.last_reply_at = utcnow()
    record(
        session,
        case,
        "ReplyReceived",
        actor,
        f"Added by {actor.name}: {reply.summary}",
        payload={"reply_id": str(reply.id), "attributed_to": reply.sender, "versions": reply.version_ids},
    )
    bump(case)
    reopen_if_complete(session, case, actor, "new uploaded documents or reply")
    apply_checks(session, case, actor, resolve=False)
    return reply, True
