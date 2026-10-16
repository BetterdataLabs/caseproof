"""User-facing review stages derived from saved runs, calls and audit evidence.

Keep the execution log intact, including older runs whose `waiting` outcome also
meant an internal continuation. Never use today's case status for a past stage.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select

from .evidence import ROLE_LABEL
from .models import AuditEvent, Job, ProviderCall

CONTINUATIONS = {
    "Continue after reading an uploaded document",
    "Continue after document appearance review",
    "Continue after policy assessment",
    "Continue after public company research",
}
REVIEW_TITLES = {
    "CaseCreated": "Initial document review",
    "EvidenceReceived": "Review new documents",
    "ReplyReceived": "Review business reply",
    "HumanDecisionRecorded": "Continue after reviewer decision",
    "RecoveryRequested": "Resume review",
    "ReviewReopened": "Reopened review",
    "ModeChanged": "Review after automation change",
    "PolicyUpdated": "Review updated requirements",
    "DocumentChecksEnabled": "Document appearance review",
}
INPUT_EVENTS = {
    "ReplyReceived",
    "EvidenceReceived",
    "HumanDecisionRecorded",
    "AutomationResumed",
    "ReviewReopened",
    "AutomationModeChanged",
    "CreditResearchRequested",
    "VendorContactChanged",
}
STAGE_EVENTS = {
    "EvidenceReady",
    "EvidenceRejected",
    "PolicyCriteriaAssessed",
    "DocumentAppearanceChecked",
    "CreditResearchUpdated",
}


def stage_for(run, calls, events, actions, versions) -> dict[str, Any]:
    """Present actual saved work, including failures swallowed by an optional stage."""
    purposes = {c.purpose for c in calls}
    by_type = {e.event_type: e for e in events}
    stage, title, summary = "actions", "Review next steps", run.summary or ""
    state = "done"
    continues = False
    document = by_type.get("EvidenceRejected") or by_type.get("EvidenceReady")
    policy = by_type.get("PolicyCriteriaAssessed")
    appearance = by_type.get("DocumentAppearanceChecked")
    research = by_type.get("CreditResearchUpdated")

    if not actions and (document or purposes & {"transcribe_document", "extract_document", "extract_pdf"}):
        stage, title, continues = "document", "Read document pages", True
        summary = "Reading document content for assessment."
        if document:
            version = versions.get(document.payload.get("version_id"))
            if version:
                title = f"Read {ROLE_LABEL.get(version.source_role, 'document').lower()} · {version.label}"
            if document.event_type == "EvidenceRejected":
                state = "needs_review"
                summary = document.summary
            else:
                summary = "Content extracted and saved for review."
        elif run.ended_at:
            summary = "Page content saved. Reading continues with the remaining pages."
    elif not actions and (policy or purposes & {"plan_document_calculations", "review_policy_criteria"}):
        stage, title, continues = "checks", "Check document requirements", True
        summary = "Checking calculations and supporting evidence."
        if policy:
            results = list(policy.payload.get("results", {}).values())
            gaps = sum(r.get("result") != "pass" for r in results)
            summary = f"{len(results)} requirement{'s' if len(results) != 1 else ''} checked. " + (
                f"{gaps} {'needs' if gaps == 1 else 'need'} follow-up."
                if gaps
                else "All requirements passed."
            )
            state = "needs_review" if gaps else "done"
    elif not actions and (appearance or "review_document_appearance" in purposes):
        stage, title, continues = "appearance", "Check document appearance", True
        summary = appearance.summary if appearance else "Checking document appearance."
        if appearance and appearance.payload.get("review", {}).get("status") == "review_required":
            state = "needs_review"
    elif not actions and (research or purposes & {"credit_public_search", "credit_research_synthesis"}):
        stage, title, continues = "research", "Research company", True
        status = research.payload.get("status") if research else None
        if status == "failed":
            state, title = "failed", "Company research failed"
            summary = "Company research could not be completed. Document review can continue."
        elif status == "complete":
            summary = "Public company research completed and saved."
        elif run.ended_at:
            summary = "Research findings saved for the next step."
        else:
            summary = "Reviewing public company information."
    else:
        # Older runs may have a summary but no provider or stage audit record.
        prefixes = (
            ("Uploaded documents processed", "document", "Read documents"),
            ("Policy criteria assessed", "checks", "Check document requirements"),
            ("Optional document appearance", "appearance", "Check document appearance"),
            ("Public company research progress", "research", "Research company"),
        )
        for prefix, kind, label in prefixes:
            if not actions and summary.startswith(prefix):
                stage, title, continues = kind, label, True
                break

    if stage == "actions":
        successful = {a["tool"]: a for a in actions if not a["shadow"]}
        wait = successful.get("wait_for_event")
        if wait and wait["result_code"] == "WAITING":
            customer = wait["args"].get("event", "customer_reply") == "customer_reply"
            state = "waiting" if customer else "human_task"
            title = "Request follow-up" if customer else "Request reviewer decision"
            summary = "Waiting for the business to reply." if customer else "Waiting for a reviewer decision."
            issued = successful.get("issue_request")
            if customer and issued and issued["result_code"] in {"ISSUED", "ALREADY_ISSUED"}:
                summary = "Request sent. " + summary
        elif run.outcome in {"completed", "human_task", "shadow", "no_action"}:
            state = run.outcome
            title, summary = {
                "completed": ("Complete document review", "The review summary is ready."),
                "human_task": ("Request reviewer decision", "A reviewer decision is needed to continue."),
                "shadow": ("Prepare review proposal", "Proposed actions saved for review."),
                "no_action": ("Review next steps", "No further action was recorded."),
            }[state]
        elif not summary:
            summary = "Reviewing the case and deciding the next step."
        # An unverified legacy `waiting` value must not claim a customer request exists.
        elif run.outcome == "waiting":
            state = "done"

    if not run.ended_at:
        state = "working"
    elif run.outcome in {"paused", "stale", "failed"}:
        state = run.outcome
        summary = {
            "paused": "Processing paused. Completed work is saved.",
            "stale": "This step was superseded. Its results were not applied.",
            "failed": "This step could not be completed.",
        }[state]
        continues = False
    return {
        "stage": stage,
        "title": title,
        "summary": summary,
        "state": state,
        "continues": continues,
        "cost_known": all(c.cost_usd is not None for c in calls),
    }


def review_activity(session, case_id, runs, actions, versions) -> dict:
    if not runs:
        return {}
    ordered = sorted(runs, key=lambda r: r.started_at)
    calls = defaultdict(list)
    for call in session.scalars(select(ProviderCall).where(ProviderCall.run_id.in_([r.id for r in runs]))):
        calls[call.run_id].append(call)
    jobs = {j.id: j for j in session.scalars(select(Job).where(Job.id.in_([r.job_id for r in runs])))}
    events = list(
        session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.case_id == case_id,
                AuditEvent.created_at >= ordered[0].started_at,
                AuditEvent.event_type.in_(STAGE_EVENTS | INPUT_EVENTS),
            )
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
    )
    by_version = {str(v.id): v for v in versions}
    result, previous = {}, None
    review_id, review_title = "", ""
    for run in ordered:
        own_events = [
            e
            for e in events
            if e.created_at >= run.started_at and (run.ended_at is None or e.created_at <= run.ended_at)
        ]
        activity = stage_for(run, calls[run.id], own_events, actions[run.id], by_version)
        job = jobs.get(run.job_id)
        detail = job.trigger_detail if job else ""
        interrupted = previous and any(
            e.event_type in INPUT_EVENTS and previous.started_at < e.created_at <= run.started_at
            for e in events
        )
        joins = (
            previous is not None
            and run.trigger == "Continuation"
            and detail in CONTINUATIONS
            and result[previous.id]["continues"]
            and not interrupted
            and previous.mode == run.mode
            and previous.controller == run.controller
        )
        if not joins:
            review_id = str(run.id)
            review_title = REVIEW_TITLES.get(run.trigger, "Document review")
            if detail == "Retry public company research":
                review_title = "Retry company research"
            elif detail == "worker lease expired":
                review_title = "Resume interrupted review"
        result[run.id] = {**activity, "review_id": review_id, "review_title": review_title}
        previous = run
    return result
