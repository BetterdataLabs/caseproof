"""Policy criteria, evidence dependencies and completion gates for Gemini assessments."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from .catalog import sample_policy
from .checks import CheckResult
from .history import record
from .models import DocumentVersion, HumanTask, MaterialClaim, PolicyVersion
from .review_defaults import LEGACY_DELIVERY_CRITERIA, LEGACY_INVOICE_CRITERIA, current_requirements

REVIEW_DECISIONS = ["accept_policy_review", "authorise_request", "keep_on_hold"]


def model_requirements(definition: dict, *, all_requirements: bool = False) -> list[dict]:
    if all_requirements:
        return current_requirements(definition)
    core = {r["key"]: r for r in sample_policy()["requirements"]}
    return [
        r
        for r in definition["requirements"]
        if r["key"] not in core
        or r["description"]
        not in {core[r["key"]]["description"], LEGACY_INVOICE_CRITERIA, LEGACY_DELIVERY_CRITERIA}
    ]


def review_input(session, case) -> dict:
    policy = session.get(PolicyVersion, case.policy_id)
    requirements = model_requirements(policy.definition, all_requirements=case.scenario_key == "uploaded")
    sources = []
    versions = list(
        session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.case_id == case.id)
            .order_by(DocumentVersion.sequence)
        ).scalars()
    )
    current_documents = {v.document_id for v in versions if v.is_active}
    for v in versions:
        historical = v.state == "superseded" and v.document_id in current_documents
        if (
            v.source_role not in {"invoice", "delivery_receipt"}
            or v.state == "withdrawn"
            or (v.state == "superseded" and not historical)
            or v.duplicate_of_id
            or v.coverage == "not_required"
        ):
            continue
        # Rejected/unreadable and pending documents remain visible as limitations, never as passing evidence.
        sources.append(
            {
                "id": str(v.id),
                "label": v.label,
                "role": v.source_role,
                "sha256": v.sha256,
                "state": v.state,
                "active": v.is_active,
                "usage": "comparison_only" if historical else "current_evidence",
                "text": v.text_content or "",
                "limitation": v.reject_detail or "",
                "pages": ((v.structured or {}).get("extraction") or {}).get("pages", []),
                "reading_limitations": ((v.structured or {}).get("extraction") or {}).get("limitations", []),
                "document_type": ((v.structured or {}).get("extraction") or {}).get(
                    "document_type", v.source_role
                ),
                "replaces_version": v.replaces_version_no,
                "version": v.version_no,
                "replaces_source_id": next(
                    (
                        str(old.id)
                        for old in versions
                        if old.document_id == v.document_id
                        and old.version_no == v.replaces_version_no
                        and old.state == "superseded"
                    ),
                    None,
                ),
                "document_id": str(v.document_id),
            }
        )
    payload = {
        "review_engine": "document-review/4" if case.scenario_key == "uploaded" else "policy-review/1",
        "llm_core": case.scenario_key == "uploaded",
        "retained_claims": [
            {
                "id": str(c.id),
                "requirement_key": c.requirement_key,
                "statement": c.statement,
                "conditions": c.conditions,
            }
            for c in session.execute(
                select(MaterialClaim).where(
                    MaterialClaim.case_id == case.id, MaterialClaim.status.in_(("retained", "satisfied"))
                )
            ).scalars()
        ],
        "policy_id": str(policy.id),
        "policy_version": policy.version,
        "requirements": requirements,
        "sources": sources,
        "case": {
            "invoice": case.invoice_reference,
            "seller": case.seller["name"],
            "buyer": case.buyer["name"],
            "submission_date": case.created_at.date().isoformat(),
        },
    }
    payload["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def combine_checks(session, case, results: dict[str, CheckResult]) -> dict[str, CheckResult]:
    data = review_input(session, case)
    if not data["requirements"]:
        return results
    report = case.policy_review or {}
    current = report.get("fingerprint") == data["fingerprint"]
    for rule in data["requirements"]:
        key = rule["key"]
        finding = report.get("results", {}).get(key) if current else None
        status = finding["result"] if finding else "pending"
        disposition = (finding or {}).get("disposition")
        if disposition:
            status = "pass"
        codes = {
            "pass": "POLICY_MET",
            "fail": "POLICY_ISSUE",
            "missing": "POLICY_EVIDENCE_MISSING",
            "review_required": "POLICY_REVIEW_REQUIRED",
            "pending": "POLICY_REVIEW_PENDING",
        }
        refs = list(dict.fromkeys(c["source_id"] for c in (finding or {}).get("citations", [])))
        assessment = {
            "criteria": rule["description"],
            "result": status,
            "detail": (finding or {}).get(
                "detail", "Gemini will assess this rule against the current documents."
            ),
            "citations": (finding or {}).get("citations", []),
            "disposition": disposition,
            "calculations": (finding or {}).get("calculations", []),
            "changes": (finding or {}).get("changes", []),
        }
        check = results.get(key)
        if check:
            check.metrics = {**check.metrics, "policy_assessment": assessment}
            # Written criteria cannot waive the core arithmetic, identity or receipt rules.
            if check.result != "pass":
                continue
        detail = assessment["detail"]
        if disposition:
            detail += f" Reviewer disposition: {disposition['reason']}"
        results[key] = CheckResult(
            key,
            "blocked" if status == "review_required" else status,
            codes[status],
            detail,
            list(dict.fromkeys([*(check.evidence_refs if check else []), *refs])),
            {**(check.metrics if check else {}), "policy_assessment": assessment},
            check.satisfied_claims if check else (finding or {}).get("satisfied_claims", []),
        )
    return results


def sync_review_tasks(session, case, actor) -> None:
    from .tasks import open_task

    data = review_input(session, case)
    report = case.policy_review or {}
    current = report.get("fingerprint") == data["fingerprint"]
    for task in session.execute(
        select(HumanTask).where(
            HumanTask.case_id == case.id,
            HumanTask.kind == "policy_review",
            HumanTask.state.in_(("pending", "claimed")),
        )
    ).scalars():
        if not current or not task.dedupe_key.endswith(data["fingerprint"]):
            task.state = "superseded"
            record(
                session,
                case,
                "HumanTaskSuperseded",
                actor,
                f"Policy evidence changed: {task.title}",
                payload={"task_id": str(task.id)},
            )
    if not current or case.paused_reason == "ON_HOLD":
        return
    for rule in data["requirements"]:
        finding = report["results"].get(rule["key"], {})
        if (
            finding.get("result") != "review_required"
            or finding.get("disposition")
            or finding.get("request_authorised")
        ):
            continue
        source_ids = [s["id"] for s in data["sources"] if s["role"] in rule["depends_on_roles"]]
        open_task(
            session,
            case,
            actor,
            kind="policy_review",
            requirement_keys=[rule["key"]],
            source_version_ids=source_ids,
            observation_ids=[],
            passages=[
                {"label": c["source_label"], "kind": "document", "quote": c["quote"]}
                for c in finding.get("citations", [])
            ],
            title=f"Review policy requirement: {rule['label']}",
            question=f"Does the available evidence satisfy this requirement? {rule['description']}",
            why_stopped=finding["detail"],
            proposed_action="Inspect the cited documents, record a supported interpretation, request evidence, or keep the case on hold.",
            dedupe_key=f"policy-review:{rule['key']}:{data['fingerprint']}",
        )
