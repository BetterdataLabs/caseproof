"""Retained review summaries. Completion freezes the snapshot in its own transaction; the export worker
renders exactly that snapshot (PDF and JSON describe the same frozen review), never the current documents.

The client pack is a redacted projection of that same snapshot for the submitting party: no reviewer
names, staff notes, model traces, or credit-research brief.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from html import escape
from typing import Any, Literal

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .casework import claims_of, policy_of
from .credit_research import public_report
from .document_checks import LIMITATION, public_config
from .history import utcnow
from .models import (
    AgentAction,
    AgentRun,
    Case,
    Decision,
    DocumentVersion,
    Export,
    HumanTask,
    InfoRequest,
    Question,
    Reply,
    RequestItem,
    User,
)
from .policies import definition_for
from .storage import object_store

NAVY = colors.HexColor("#112d3c")
TEAL = colors.HexColor("#00675f")
MUTED = colors.HexColor("#52656c")
RULE = colors.HexColor("#d8e2e0")
SOFT = colors.HexColor("#eef4f1")


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def build_snapshot(session: Session, case: Case) -> dict[str, Any]:
    policy = policy_of(session, case)
    requirements = {r["key"]: r for r in definition_for(policy)["requirements"]}
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
    questions = (
        session.execute(
            select(Question).where(Question.case_id == case.id).order_by(Question.requirement_key.desc())
        )
        .scalars()
        .all()
    )
    requests = (
        session.execute(select(InfoRequest).where(InfoRequest.case_id == case.id).order_by(InfoRequest.round))
        .scalars()
        .all()
    )
    tasks = (
        session.execute(select(HumanTask).where(HumanTask.case_id == case.id).order_by(HumanTask.created_at))
        .scalars()
        .all()
    )
    decisions = {
        d.task_id: d for d in session.execute(select(Decision).where(Decision.case_id == case.id)).scalars()
    }
    users = {u.id: u.display_name for u in session.execute(select(User)).scalars()}
    runs = (
        session.execute(select(AgentRun).where(AgentRun.case_id == case.id).order_by(AgentRun.started_at))
        .scalars()
        .all()
    )
    action_count = session.execute(select(AgentAction.id).where(AgentAction.case_id == case.id)).all()
    replies = (
        session.execute(select(Reply).where(Reply.case_id == case.id).order_by(Reply.created_at))
        .scalars()
        .all()
    )
    return {
        "schema": "caseproof.review-summary/1",
        "document_checks": public_config(case.document_checks),
        "credit_research": public_report(case.credit_research),
        "policy_review": case.policy_review,
        "case": {
            "id": str(case.id),
            "reference": case.reference,
            "title": case.title,
            "revision": case.revision,
            "invoice_reference": case.invoice_reference,
            "facility_reference": case.facility_reference,
            "seller": case.seller["name"],
            "buyer": case.buyer["name"],
            "receipt_sources": [p["name"] for p in case.permitted_receipt_issuers],
        },
        "policy": {
            "key": policy.key,
            "version": policy.version,
            "name": policy.name,
            "notice": policy.definition.get("notice"),
        },
        "outcome": "Document review complete. The financing decision remains with the bank.",
        "questions": [
            {
                "key": q.requirement_key,
                "label": q.label,
                "criteria": requirements[q.requirement_key]["description"],
                "policy_assessment": (q.metrics or {}).get("policy_assessment"),
                "state": q.state,
                "result": q.check_result,
                "reason_code": q.reason_code,
                "detail": q.detail,
                "evidence": [labels.get(uuid.UUID(e), e) for e in q.evidence_refs or []],
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
        "sources": [
            {
                "label": v.label,
                "role": v.source_role,
                "version": v.version_no,
                "state": v.state,
                "active": v.is_active,
                "coverage": v.coverage,
                "sha256": v.sha256,
                "received_via": v.received_via,
                "duplicate_of": labels.get(v.duplicate_of_id) if v.duplicate_of_id else None,
                "note": v.reject_detail,
                "received_at": _iso(v.created_at),
                "visual_review": v.visual_review,
            }
            for v in versions
        ],
        "requests": [
            {
                "round": r.round,
                "state": r.state,
                "issued_at": _iso(r.issued_at),
                "reminder_sent_at": _iso(r.reminder_sent_at),
                "items": [
                    i.text
                    for i in session.execute(
                        select(RequestItem).where(
                            RequestItem.request_id == r.id, RequestItem.status != "discarded"
                        )
                    ).scalars()
                ],
            }
            for r in requests
            if r.state != "draft"
        ],
        "replies": [
            {
                "summary": r.summary,
                "sender": r.sender,
                "received_at": _iso(r.created_at),
                "sources": [labels.get(uuid.UUID(v), v) for v in r.version_ids],
            }
            for r in replies
        ],
        "human_decisions": [
            {
                "task": t.title,
                "kind": t.kind,
                "decision": decisions[t.id].decision_type,
                "reason": decisions[t.id].reason,
                "conditions": decisions[t.id].conditions,
                "by": users.get(decisions[t.id].actor_id, ""),
                "at": _iso(decisions[t.id].created_at),
                "covered_sources": [labels.get(uuid.UUID(v), v) for v in decisions[t.id].covered_version_ids],
            }
            for t in tasks
            if t.id in decisions
        ],
        "retained_claims": [
            {"statement": c.statement, "status": c.status, "conditions": c.conditions}
            for c in claims_of(session, case.id)
        ],
        "automation": {
            "runs": len(runs),
            "agent_actions": len(action_count),
            "model_calls": sum(r.model_calls for r in runs),
            "model_cost_usd": str(sum((r.cost_usd for r in runs), start=0)),
            "controllers": sorted({r.controller for r in runs}),
        },
        "frozen_at": utcnow().isoformat(),
        "boundary": "Bank credit decisions, formal sanctions screening, authenticity investigations, facility changes, financing approval and payments "
        "remain in the bank's existing process.",
    }


CLIENT_NOTICE = (
    "This notice is for the submitting party. It records the document-review outcome on this "
    "invoice pack. It does not name bank staff, include model traces, or disclose the bank's "
    "credit research. The financing decision remains with the bank."
)


def client_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """What the submitting party may see: checklist outcome, their documents, and requests they already received."""
    case = snapshot["case"]
    policy = snapshot["policy"]
    return {
        "schema": "caseproof.client-summary/1",
        "audience": "submitting_party",
        "notice": CLIENT_NOTICE,
        "case": {
            "reference": case["reference"],
            "title": case["title"],
            "revision": case["revision"],
            "invoice_reference": case["invoice_reference"],
            "seller": case["seller"],
            "buyer": case["buyer"],
        },
        "policy": {"name": policy["name"], "key": policy["key"], "version": policy["version"]},
        "outcome": snapshot["outcome"],
        "questions": [
            {
                "label": q["label"],
                "state": q["state"],
                "result": q["result"],
                "reason_code": q["reason_code"],
                "detail": (
                    "This requirement was resolved during bank review."
                    if (q.get("policy_assessment") or {}).get("disposition")
                    else q["detail"].split(" Reviewer disposition:", 1)[0]
                ),
                "evidence": q["evidence"],
            }
            for q in snapshot["questions"]
        ],
        "sources": [
            {
                "label": s["label"],
                "role": s["role"],
                "version": s["version"],
                "state": s["state"],
                "active": s["active"],
                "sha256": s["sha256"],
                "received_via": s.get("received_via"),
                "duplicate_of": s.get("duplicate_of"),
                "received_at": s.get("received_at"),
            }
            for s in snapshot["sources"]
        ],
        "requests": snapshot.get("requests") or [],
        "replies": [
            {
                "summary": r["summary"],
                "received_at": r["received_at"],
                "sources": r["sources"],
            }
            for r in snapshot.get("replies") or []
        ],
        "frozen_at": snapshot["frozen_at"],
        "boundary": snapshot["boundary"],
    }


def client_artifact(export: Export, fmt: Literal["pdf", "json"]) -> bytes:
    """Deterministic client pack from the frozen snapshot. No staff names or model traces."""
    client = client_snapshot(export.snapshot)
    if fmt == "pdf":
        return render_client_pdf(export.export_ref, client)
    return json.dumps(
        {"export_id": str(export.id), "export_ref": export.export_ref, **client},
        indent=2,
        sort_keys=True,
    ).encode()


def render_pdf(export_ref: str, snapshot: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"CaseProof review summary {export_ref}",
        author="CaseProof",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=NAVY,
        alignment=TA_LEFT,
    )
    small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=10, textColor=MUTED)
    h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=21)
    h2 = ParagraphStyle(
        "h2",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=TEAL,
        spaceBefore=10,
        spaceAfter=4,
    )
    c = snapshot["case"]
    story: list[Any] = [
        Paragraph("CaseProof · Document review summary", small),
        Spacer(1, 4),
        Paragraph(escape(f"{c['reference']} — {c['title']}"), h1),
        Spacer(1, 4),
        Paragraph(escape(snapshot["outcome"]), body),
        Spacer(1, 8),
    ]
    meta = [
        ["Export ID", export_ref, "Case revision", str(c["revision"])],
        ["Seller", c["seller"], "Buyer", c["buyer"]],
        ["Invoice", c["invoice_reference"], "Facility", c["facility_reference"]],
        [
            "Policy",
            f"{snapshot['policy']['key']} v{snapshot['policy']['version']}",
            "Frozen at",
            snapshot["frozen_at"][:19] + "Z",
        ],
    ]
    story.append(_table(meta, [28 * mm, 58 * mm, 28 * mm, 60 * mm], body, header=False))
    story.append(Paragraph("Checklist", h2))
    rows = [["Requirement", "Result", "Evidence", "Basis"]]
    for q in snapshot["questions"]:
        rows.append(
            [
                Paragraph(escape(q["label"]), body),
                q["state"].replace("_", " "),
                ", ".join(q["evidence"]),
                Paragraph(escape(q["detail"]), small),
            ]
        )
    story.append(_table(rows, [48 * mm, 20 * mm, 22 * mm, 84 * mm], body))
    assessed = [q for q in snapshot["questions"] if q.get("policy_assessment")]
    if assessed:
        story.append(Paragraph("Policy criteria and supporting evidence", h2))
        for q in assessed:
            story.append(Paragraph(escape(q["label"]), body))
            story.append(Paragraph(escape(q["criteria"]), small))
            assessment = q["policy_assessment"]
            story.append(Paragraph(escape(assessment["detail"]), small))
            for citation in assessment.get("citations", []):
                story.append(Paragraph(escape(f"{citation['source_label']}: {citation['quote']}"), small))
            for calculation in assessment.get("calculations", []):
                detail = (
                    f"{calculation.get('result', '')} {calculation.get('unit', '')}"
                    if calculation.get("status") == "calculated"
                    else calculation.get("error", "Needs review")
                )
                if calculation.get("comparison"):
                    detail += f"; compared with {calculation['expected_result']} {calculation.get('unit', '')}; {calculation['comparison']}; difference {calculation['difference']}"
                prefix = "Previous version: " if calculation.get("usage") == "comparison_only" else ""
                story.append(Paragraph(escape(f"{prefix}{calculation['description']}: {detail}"), small))
            for change in assessment.get("changes", []):
                story.append(
                    Paragraph(
                        escape(
                            f"{change['original_source']} to {change['replacement_source']}: {change['summary']}"
                        ),
                        small,
                    )
                )
            if assessment.get("disposition"):
                disposition = assessment["disposition"]
                story.append(
                    Paragraph(
                        escape(f"Reviewed by {disposition['reviewed_by']}: {disposition['reason']}"), small
                    )
                )
            story.append(Spacer(1, 3 * mm))
    if snapshot.get("document_checks", {}).get("enabled"):
        story.append(Paragraph("Optional document appearance checks", h2))
        story.append(Paragraph(escape(LIMITATION), small))
        for source in snapshot["sources"]:
            review = source.get("visual_review")
            if not review:
                continue
            story.append(
                Paragraph(
                    escape(
                        f"{source['label']}: {review['status'].replace('_', ' ')}. {review.get('summary', '')}"
                    ),
                    body,
                )
            )
            if review.get("template_name"):
                story.append(
                    Paragraph(
                        escape(
                            f"Reference: {review['template_name']} · SHA-256 {review.get('template_sha256', '')}"
                        ),
                        small,
                    )
                )
            for finding in review.get("findings", []):
                story.append(
                    Paragraph(
                        escape(f"Page {finding['page']} — {finding['title']}: {finding['detail']}"), small
                    )
                )
            if review.get("reviewed_by"):
                story.append(
                    Paragraph(
                        escape(f"Reviewed by {review['reviewed_by']}: {review.get('review_reason', '')}"),
                        small,
                    )
                )
    research = snapshot.get("credit_research", {})
    if research.get("enabled"):
        story.append(Paragraph("Public company credit research", h2))
        subject = research.get("subject", {})
        story.append(
            Paragraph(
                escape(
                    f"{subject.get('name', research['target'])} · {research.get('country', '')} · {research.get('status', '')}"
                ),
                body,
            )
        )
        story.append(
            Paragraph(
                escape(research.get("summary") or research.get("error") or "Research has not completed."),
                body,
            )
        )
        story.append(Paragraph(escape(research["limitation"]), small))
        story.append(
            Paragraph(
                escape(
                    f"As of {research.get('completed_at', research['requested_at'])} · Method {research['method']} · Model {research.get('model', 'not called')}"
                ),
                small,
            )
        )
        for dimension in research.get("dimensions", []):
            story.append(
                Paragraph(escape(f"{dimension['label']} — {dimension['signal'].replace('_', ' ')}"), h2)
            )
            story.append(Paragraph(escape(dimension["analysis"]), body))
            for citation in dimension["citations"]:
                story.append(
                    Paragraph(escape(f"{', '.join(citation['sources'])}: {citation['quote']}"), small)
                )
        for search in research.get("searches", []):
            for source in search["sources"]:
                story.append(
                    Paragraph(
                        f'{escape(source["id"])}: {escape(source["title"])} — <link href="{escape(source["url"], quote=True)}">{escape(source["url"])}</link>',
                        small,
                    )
                )
        if research.get("information_to_obtain"):
            story.append(Paragraph("Information the bank still needs", h2))
            for item in research["information_to_obtain"]:
                story.append(Paragraph(escape(item), body))
    story.append(Paragraph("Sources", h2))
    rows = [["Source", "Role", "Version", "Status", "SHA-256 (prefix)"]]
    for s in snapshot["sources"]:
        status = (
            s["state"]
            + (" · active" if s["active"] else "")
            + (
                f" · {s['coverage'].replace('_', ' ')}"
                if s["coverage"] in ("reviewed", "not_required")
                else ""
            )
            + (f" · copy of {s['duplicate_of']}" if s["duplicate_of"] else "")
        )
        rows.append(
            [
                s["label"],
                s["role"].replace("_", " "),
                str(s["version"] or ""),
                Paragraph(status, small),
                (s["sha256"] or "")[:16],
            ]
        )
    story.append(_table(rows, [16 * mm, 34 * mm, 16 * mm, 66 * mm, 42 * mm], body))
    if snapshot["requests"]:
        story.append(Paragraph("Requests sent to the business (simulated inbox)", h2))
        for r in snapshot["requests"]:
            items = "<br/>".join(f"• {escape(i)}" for i in r["items"])
            story.append(
                KeepTogether(
                    [
                        Paragraph(
                            f"<b>Round {r['round']}</b> · {r['state']} · issued {(r['issued_at'] or '')[:16]}",
                            body,
                        ),
                        Paragraph(items, small),
                        Spacer(1, 4),
                    ]
                )
            )
    if snapshot["replies"]:
        story.append(Paragraph("Replies received", h2))
        rows = [["Received", "From", "Content", "Sources"]]
        for r in snapshot["replies"]:
            rows.append(
                [
                    (r["received_at"] or "")[:16],
                    Paragraph(escape(r["sender"]), small),
                    Paragraph(escape(r["summary"]), small),
                    ", ".join(r["sources"]),
                ]
            )
        story.append(_table(rows, [28 * mm, 44 * mm, 80 * mm, 22 * mm], body))
    if snapshot["human_decisions"]:
        story.append(Paragraph("Human decisions", h2))
        for d in snapshot["human_decisions"]:
            cond = (
                "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in d["conditions"].items())
                if d["conditions"]
                else "—"
            )
            story.append(
                KeepTogether(
                    [
                        Paragraph(
                            f"<b>{escape(d['task'])}</b> — {d['decision'].replace('_', ' ')} by {escape(d['by'])} ({(d['at'] or '')[:16]})",
                            body,
                        ),
                        Paragraph(
                            f"Reason: {escape(d['reason'])}<br/>Conditions: {escape(cond)}<br/>Covered sources: {', '.join(d['covered_sources']) or '—'}",
                            small,
                        ),
                        Spacer(1, 4),
                    ]
                )
            )
    else:
        story.append(
            KeepTogether(
                [
                    Paragraph("Human decisions", h2),
                    Paragraph(
                        "No human decision was required: routine evidence completed automatically.", body
                    ),
                ]
            )
        )
    a = snapshot["automation"]
    story.append(
        KeepTogether(
            [
                Paragraph("Automation record", h2),
                Paragraph(
                    f"{a['runs']} agent run(s), {a['agent_actions']} recorded tool actions, {a['model_calls']} model "
                    f"calls, model cost USD {a['model_cost_usd']}. Controllers: {', '.join(a['controllers']) or '—'}.",
                    body,
                ),
            ]
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(snapshot["boundary"]), small))
    story.append(Paragraph(escape(snapshot["policy"].get("notice") or ""), small))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, f"{export_ref} · revision {c['revision']} · document review")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_client_pdf(export_ref: str, snapshot: dict[str, Any]) -> bytes:
    """Shorter notice for the submitting party: outcome, checklist, sources, and the exchange they already saw."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"CaseProof client review notice {export_ref}",
        author="CaseProof",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=NAVY,
        alignment=TA_LEFT,
    )
    small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=10, textColor=MUTED)
    h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=21)
    h2 = ParagraphStyle(
        "h2",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=TEAL,
        spaceBefore=10,
        spaceAfter=4,
    )
    c = snapshot["case"]
    story: list[Any] = [
        Paragraph("CaseProof · Client document-review notice", small),
        Spacer(1, 4),
        Paragraph(escape(f"{c['reference']} — {c['title']}"), h1),
        Spacer(1, 4),
        Paragraph(escape(snapshot["outcome"]), body),
        Spacer(1, 4),
        Paragraph(escape(snapshot["notice"]), small),
        Spacer(1, 8),
    ]
    story.append(
        _table(
            [
                ["Notice ID", export_ref, "Case revision", str(c["revision"])],
                ["Seller", c["seller"], "Buyer", c["buyer"]],
                ["Invoice", c["invoice_reference"], "Policy", snapshot["policy"]["name"]],
                [
                    "Frozen at",
                    snapshot["frozen_at"][:19] + "Z",
                    "Audience",
                    "Submitting party",
                ],
            ],
            [28 * mm, 58 * mm, 28 * mm, 60 * mm],
            body,
            header=False,
        )
    )
    story.append(Paragraph("Checklist", h2))
    rows = [["Requirement", "Result", "Evidence", "Basis"]]
    for q in snapshot["questions"]:
        rows.append(
            [
                Paragraph(escape(q["label"]), body),
                q["state"].replace("_", " "),
                ", ".join(q["evidence"]),
                Paragraph(escape(q["detail"]), small),
            ]
        )
    story.append(_table(rows, [48 * mm, 20 * mm, 22 * mm, 84 * mm], body))
    story.append(Paragraph("Documents on this submission", h2))
    rows = [["Source", "Role", "Version", "Status", "SHA-256 (prefix)"]]
    for s in snapshot["sources"]:
        status = (
            s["state"]
            + (" · active" if s["active"] else "")
            + (f" · copy of {s['duplicate_of']}" if s["duplicate_of"] else "")
        )
        rows.append(
            [
                s["label"],
                s["role"].replace("_", " "),
                str(s["version"] or ""),
                Paragraph(status, small),
                (s["sha256"] or "")[:16],
            ]
        )
    story.append(_table(rows, [16 * mm, 34 * mm, 16 * mm, 66 * mm, 42 * mm], body))
    if snapshot["requests"]:
        story.append(Paragraph("Requests you received", h2))
        for r in snapshot["requests"]:
            items = "<br/>".join(f"• {escape(i)}" for i in r["items"])
            story.append(
                KeepTogether(
                    [
                        Paragraph(
                            f"<b>Round {r['round']}</b> · {r['state']} · issued {(r['issued_at'] or '')[:16]}",
                            body,
                        ),
                        Paragraph(items, small),
                        Spacer(1, 4),
                    ]
                )
            )
    if snapshot["replies"]:
        story.append(Paragraph("Replies you sent", h2))
        rows = [["Received", "Content", "Sources"]]
        for r in snapshot["replies"]:
            rows.append(
                [
                    (r["received_at"] or "")[:16],
                    Paragraph(escape(r["summary"]), small),
                    ", ".join(r["sources"]),
                ]
            )
        story.append(_table(rows, [28 * mm, 116 * mm, 30 * mm], body))
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(snapshot["boundary"]), small))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, f"{export_ref} · revision {c['revision']} · client notice")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _table(rows: list[list[Any]], widths: list[float], body: ParagraphStyle, header: bool = True) -> Table:
    rows = [
        [Paragraph(escape(cell), body) if isinstance(cell, str) else cell for cell in row] for row in rows
    ]
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SOFT), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8)]
    else:
        style += [
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.5),
            ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8.5),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ]
    table.setStyle(TableStyle(style))
    return table


def render_export(session: Session, export: Export) -> None:
    """Staged publication: write private objects, verify, then publish the reference."""
    case = session.get(Case, export.case_id)
    assert case is not None
    export.attempts += 1
    pdf = render_pdf(export.export_ref, export.snapshot)
    payload = json.dumps(
        {"export_id": str(export.id), "export_ref": export.export_ref, **export.snapshot},
        indent=2,
        sort_keys=True,
    ).encode()
    base = f"orgs/{export.org_id}/cases/{export.case_id}/exports/{export.export_ref}"
    store = object_store()
    store.put_immutable(base + ".pdf", pdf)
    store.put_immutable(base + ".json", payload)
    if hashlib.sha256(store.get(base + ".pdf")).hexdigest() != hashlib.sha256(pdf).hexdigest():
        raise RuntimeError("export verification failed")
    export.pdf_key = base + ".pdf"
    export.json_key = base + ".json"
    export.pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    if export.state == "preparing":
        # A case that changed before publication keeps this as a historical, superseded export.
        export.state = (
            "ready" if case.current_export_id == export.id and case.lifecycle == "complete" else "superseded"
        )
        export.ready_at = utcnow()
