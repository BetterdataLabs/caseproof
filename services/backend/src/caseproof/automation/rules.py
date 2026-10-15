"""Fixed-rule controller: the deterministic baseline workflow for evaluation and tests.

It uses the same tools and domain rules as the agent but no language model. It cannot interpret a written
message, so every message goes to a person without a comparison. It is never presented as the agent.
"""

from __future__ import annotations

from .gateway import RunContext
from .tools import CaseTools

HUMAN_REASONS = {
    "CUMULATIVE_RECEIPT",
    "CONFLICTING_DELIVERY_EVENT",
    "CONDITIONS_NOT_MET",
    "OVER_RECEIPT",
    "RECEIPT_MISMATCH",
    "PARTY_MISMATCH",
    "REFERENCE_MISMATCH",
    "REPLACEMENT_REJECTED",
}
ANSWERED_BADLY = {
    "CONDITIONS_NOT_MET",
}  # the outstanding request was answered unusably


async def run_rules(ctx: RunContext) -> str:
    tools = CaseTools(ctx)
    snap = tools.read_case("Fixed-rule workflow: load case")["case"]
    pending_messages = [s["label"] for s in snap["sources"] if s["coverage"] == "needs_review"]
    checks = tools.run_checks("Fixed-rule workflow: recheck evidence")
    if ctx.terminal:
        return "stopped"
    results = {q["requirement"]: q for q in checks.get("questions", [])}
    if not pending_messages and all(q["result"] == "pass" for q in results.values()):
        done = tools.try_complete("Fixed-rule workflow: all checks pass")
        if done.get("result") == "COMPLETED" or ctx.terminal:
            return "completed"
    snap = tools.read_case("Fixed-rule workflow: reload after checks")["case"]
    requestable = [
        q
        for q in snap["questions"]
        if q["state"] != "resolved"
        and not q["covered_by_outstanding_request"]
        and q["request_templates_allowed"]
    ]
    if requestable:
        prepared = tools.prepare_request(
            [q["requirement"] for q in requestable],
            [q["request_templates_allowed"][0] for q in requestable],
            "Fixed-rule workflow: request missing evidence",
        )
        if prepared.get("request_id"):
            tools.issue_request(prepared["request_id"], "Fixed-rule workflow: send request")
        if ctx.terminal:
            return "stopped"
    if pending_messages:
        tools.open_human_task(
            "message_review",
            "Written message needs review",
            "A written message was received. Review it and record a disposition.",
            "The fixed-rule workflow cannot interpret free text.",
            "Continue checks after the decision.",
            ["delivery_receipts"],
            pending_messages,
            [],
            "Fixed-rule workflow: free text needs a person",
        )
        return "human_task"
    snap = tools.read_case("Fixed-rule workflow: decide next step")["case"]
    blocked = [
        q
        for q in snap["questions"]
        if q["state"] != "resolved"
        and q["state"] != "waiting_decision"
        and q["reason_code"] in HUMAN_REASONS
        and not q["request_templates_allowed"]
        and (not q["covered_by_outstanding_request"] or q["reason_code"] in ANSWERED_BADLY)
    ]
    if blocked:
        tools.open_human_task(
            "evidence_problem",
            f"Evidence problem: {blocked[0]['label']}",
            blocked[0]["detail"],
            "The evidence cannot be counted automatically.",
            "Request corrected evidence if authorised.",
            [q["requirement"] for q in blocked],
            [],
            [],
            "Fixed-rule workflow: blocked evidence",
        )
        return "human_task"
    if any(r["state"] == "issued" for r in snap["requests"]):
        tools.wait_for_event("customer_reply", "Fixed-rule workflow: waiting for the business")
        return "waiting"
    return "no_action"
