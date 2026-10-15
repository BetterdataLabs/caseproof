"""Case-scoped reference documents and human disposition of appearance findings."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pypdfium2 as pdfium
from sqlalchemy import select

from .actors import ROLE_REVIEWER, ROLE_SUPERVISOR
from .errors import Conflict, Forbidden, Unsupported
from .history import bump, record, utcnow
from .models import DocumentVersion, HumanTask
from .pdfdocs import _PDFIUM
from .storage import object_store

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .actors import Actor
    from .intake import Upload
    from .models import Case

MAX_VISUAL_PAGES = 3
VISUAL_DECISIONS = ["accept_document_appearance", "keep_on_hold"]
LIMITATION = (
    "Appearance checks can miss well-made alterations and can flag legitimate edits. "
    "They do not authenticate the issuer, validate digital signatures or prove absence of fraud."
)


def reference_page_count(data: bytes) -> int:
    try:
        with _PDFIUM, pdfium.PdfDocument(data) as document:
            count = len(document)
            if not 1 <= count <= MAX_VISUAL_PAGES:
                raise Unsupported("REFERENCE_PAGES", f"Use a reference PDF with 1–{MAX_VISUAL_PAGES} pages.")
            if any(not all(0 < n <= 20000 for n in document.get_page_size(i)) for i in range(count)):
                raise Unsupported("REFERENCE_SIZE", "The reference PDF has unsupported page dimensions.")
            return count
    except Unsupported:
        raise
    except Exception as exc:
        raise Unsupported("REFERENCE_UNREADABLE", "The reference must be an unlocked, readable PDF.") from exc


def public_config(config: dict | None) -> dict:
    config = config or {}
    return {
        "enabled": bool(config),
        "tampering": config.get("tampering", False),
        "enabled_by": config.get("enabled_by"),
        "enabled_at": config.get("enabled_at"),
        "page_limit": MAX_VISUAL_PAGES,
        "references": {
            role: {k: ref[k] for k in ("name", "sha256", "page_count")}
            for role, ref in config.get("references", {}).items()
        },
    }


def pending_review(config: dict | None, role: str) -> dict | None:
    config = config or {}
    reference = config.get("references", {}).get(role)
    if role not in {"invoice", "delivery_receipt"} or not (config.get("tampering") or reference):
        return None
    return {
        "status": "pending",
        "tampering_requested": bool(config.get("tampering")),
        "template_requested": bool(reference),
        "template_name": reference["name"] if reference else None,
        "template_sha256": reference["sha256"] if reference else None,
        "findings": [],
        "limitation": LIMITATION,
    }


def configure_checks(
    session: Session, case: Case, actor: Actor, tampering: bool, references: list[Upload]
) -> None:
    from .casework import reopen_if_complete

    if not actor.has(ROLE_REVIEWER, ROLE_SUPERVISOR):
        raise Forbidden(
            "ROLE_REQUIRED", "Only bank reviewers and supervisors can select reference documents."
        )
    if case.document_checks:
        raise Conflict(
            "CHECKS_ALREADY_SET", "These selections are fixed for this case and its later uploads."
        )
    if case.lifecycle == "archived" or case.automation_mode != "autonomous":
        raise Conflict("AUTOMATION_REQUIRED", "Enable autonomous mode on an open case before adding checks.")
    if not tampering and not references:
        raise Unsupported("CHECKS_REQUIRED", "Select the tampering check or provide a reference PDF.")
    config = {
        "tampering": tampering,
        "references": {},
        "enabled_by": actor.name,
        "enabled_at": utcnow().isoformat(),
    }
    roles = set()
    validated = []
    for upload in references:
        if upload.role not in {"invoice", "delivery_receipt"} or upload.role in roles:
            raise Unsupported("REFERENCE_ROLE", "Provide one reference per document type.")
        roles.add(upload.role)
        validated.append((upload, reference_page_count(upload.data)))
    for upload, count in validated:
        sha = hashlib.sha256(upload.data).hexdigest()
        key = f"orgs/{case.org_id}/cases/{case.id}/references/{upload.role}-{sha}.pdf"
        generation = object_store().put_immutable(key, upload.data)
        config["references"][upload.role] = {
            "name": upload.name,
            "sha256": sha,
            "page_count": count,
            "object_key": key,
            "object_generation": generation,
        }
    case.document_checks = config
    for version in session.execute(
        select(DocumentVersion).where(DocumentVersion.case_id == case.id)
    ).scalars():
        if eligible(version):
            version.visual_review = pending_review(config, version.source_role)
    reopen_if_complete(session, case, actor, "Optional document checks enabled")
    bump(case)
    record(
        session,
        case,
        "DocumentChecksEnabled",
        actor,
        "Optional document checks enabled",
        payload=public_config(config),
    )


def eligible(version: DocumentVersion) -> bool:
    return bool(
        version.mime == "application/pdf"
        and version.object_key
        and version.state not in {"superseded", "withdrawn"}
        and version.coverage != "not_required"
        and not version.duplicate_of_id
    )


def ensure_review_tasks(session: Session, case: Case, actor: Actor) -> bool:
    from .tasks import open_task

    changed = False
    for version in session.execute(
        select(DocumentVersion).where(DocumentVersion.case_id == case.id)
    ).scalars():
        review = version.visual_review or {}
        if not eligible(version) or review.get("status") != "review_required":
            continue
        _, created = open_task(
            session,
            case,
            actor,
            kind="document_review",
            requirement_keys=[],
            source_version_ids=[str(version.id)],
            observation_ids=[],
            passages=[],
            title=f"Review document appearance: {version.label}",
            question=f"Inspect {version.label}, its highlighted findings and any reference template. Can its appearance be accepted for this review, or should the case remain on hold?",
            why_stopped=review.get("summary", "The document appearance needs review."),
            proposed_action="Check the original with the issuer if needed. Record your findings or keep the case on hold for a replacement.",
            dedupe_key=f"document-review:{version.id}",
        )
        changed |= created
    return changed


def supersede_review_tasks(session: Session, case: Case, actor: Actor) -> None:
    for task in session.execute(
        select(HumanTask).where(
            HumanTask.case_id == case.id,
            HumanTask.kind == "document_review",
            HumanTask.state.in_(("pending", "claimed")),
        )
    ).scalars():
        versions = list(
            session.execute(
                select(DocumentVersion).where(
                    DocumentVersion.case_id == case.id, DocumentVersion.id.in_(task.source_version_ids)
                )
            ).scalars()
        )
        if versions and all(not eligible(v) for v in versions):
            task.state = "superseded"
            record(
                session,
                case,
                "HumanTaskSuperseded",
                actor,
                f"Replaced evidence: {task.title}",
                payload={"task_id": str(task.id)},
            )
