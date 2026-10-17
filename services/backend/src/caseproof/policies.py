"""Supervisor-owned, immutable policy versions and the settings used by each case."""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from string import Formatter
from typing import Any

from sqlalchemy import select

from .catalog import sample_policy
from .config import get_settings
from .errors import Conflict, NotFound, Unsupported
from .history import record, utcnow
from .models import OrgControl, PolicyVersion
from .review_defaults import current_requirements

# Metadata is shared with the editor; hard ceilings bound what this implementation supports.
MAX_RUN_SECONDS = 180
MAX_REQUIREMENTS = 10
CORE_KEYS = {"invoice_total", "delivery_receipts"}
POLICY_EVIDENCE_TEMPLATE = {
    "label": "Evidence for a policy requirement",
    "text": "Please provide supporting documents or clarification for invoice {invoice_number} to address {policy_title}: {policy_issue}",
}
SETTING_FIELDS = {
    "reminder_after_hours": (
        "timers",
        "First reminder after",
        "hours",
        1,
        336,
        "Time after a request before the app records a reminder.",
    ),
    "stop_after_reminder_hours": (
        "timers",
        "Escalate after reminder",
        "hours",
        1,
        336,
        "Additional waiting time before a reviewer must decide what happens next.",
    ),
    "request_rounds": (
        "limits",
        "Request rounds",
        "rounds",
        1,
        6,
        "Requests allowed before a reviewer must authorise another round.",
    ),
    "case_budget_usd": (
        "limits",
        "AI budget per case",
        "USD",
        0.01,
        10,
        "AI usage allowance for a new case; this is unrelated to the financing amount.",
    ),
    "automatic_wakeups_per_case": (
        "limits",
        "Agent runs per case",
        "runs",
        1,
        100,
        "How many times the agent may start work, excluding waiting time.",
    ),
    "active_seconds_per_invocation": (
        "limits",
        "Time per agent run",
        "seconds",
        10,
        MAX_RUN_SECONDS,
        "Total processing time for one run, including model requests and retries.",
    ),
    "model_calls_per_invocation": (
        "limits",
        "AI calls per run",
        "calls",
        1,
        12,
        "Includes document reading, reasoning, comparisons and retries.",
    ),
    "tool_calls_per_invocation": (
        "limits",
        "Actions per run",
        "actions",
        1,
        32,
        "Maximum tool actions, such as checking evidence or preparing a request.",
    ),
    "transient_retries": (
        "limits",
        "Retries per AI request",
        "retries",
        0,
        3,
        "Retries for temporary errors, while time and the other allowances remain.",
    ),
    "max_sources_per_case": (
        "limits",
        "Evidence versions per case",
        "versions",
        5,
        100,
        "Includes document corrections and written messages.",
    ),
    "max_pages_per_document": (
        "limits",
        "Pages per PDF",
        "pages",
        1,
        20,
        "Longer PDFs are kept but cannot be used automatically.",
    ),
    "max_bytes_per_original": (
        "limits",
        "Size per document",
        "bytes",
        1024,
        10485760,
        "Maximum file size. 1,048,576 bytes equals 1 MiB; uploads also have a 20 MiB total limit.",
    ),
}
RUNTIME_FIELDS = {
    "model_calls_per_invocation": "max_model_calls",
    "tool_calls_per_invocation": "max_tool_calls",
    "active_seconds_per_invocation": "max_active_seconds",
    "transient_retries": "max_transient_retries",
    "automatic_wakeups_per_case": "max_wakeups",
    "request_rounds": "max_request_rounds",
    "case_budget_usd": "case_budget_usd",
}


def definition_for(policy: PolicyVersion) -> dict[str, Any]:
    definition = deepcopy(policy.definition)
    definition["requirements"] = current_requirements(definition)
    definition["supported_contract"] = (
        "Business documents in supported file formats; interpreted using their stated currencies, units, line items and adjustments."
    )
    settings = get_settings()
    # Existing v1 cases retain their deployed behaviour. Versions published by the editor pin settings.
    if not definition.get("runtime_limits_version"):
        for key, attr in RUNTIME_FIELDS.items():
            value = getattr(settings, attr)
            definition["limits"][key] = str(value) if isinstance(value, Decimal) else int(value)
        for key in definition["timers"]:
            definition["timers"][key] = int(getattr(settings, key))
    definition["limits"]["environment_daily_budget_usd"] = str(settings.daily_budget_usd)
    return definition


def settings_for(session, case) -> dict[str, Any]:
    policy = session.get(PolicyVersion, case.policy_id)
    definition = definition_for(policy)
    return {**definition["limits"], **definition["timers"]}


def correction_fields(role: str, rule: dict) -> list[str]:
    """Basis changes require publication; existing case policies keep their restrictions."""
    return list(dict.fromkeys([*rule["may_change"], *(["basis"] if role == "delivery_receipt" else [])]))


def editor_schema() -> dict:
    baseline = sample_policy()
    return {
        "max_requirements": MAX_REQUIREMENTS,
        "settings": [
            {
                "key": key,
                "section": section,
                "label": label,
                "unit": unit,
                "min": low,
                "max": high,
                "hint": hint,
                "step": "0.01" if key == "case_budget_usd" else "1",
            }
            for key, (section, label, unit, low, high, hint) in SETTING_FIELDS.items()
        ],
        "replacement_fields": {
            key: correction_fields(key, value) for key, value in baseline["replacement_rules"].items()
        },
        "task_decisions": baseline["task_decisions"],
    }


def _text(value, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Unsupported("INVALID_POLICY", f"{label} must contain 1–{maximum} characters.")
    return value


def _slots(text: str) -> set[str]:
    try:
        fields = set()
        for _, name, spec, conversion in Formatter().parse(text):
            if name is not None:
                if not name.isidentifier() or spec or conversion:
                    raise ValueError
                fields.add(name)
        return fields
    except ValueError as exc:
        raise Unsupported(
            "INVALID_TEMPLATE",
            "Use plain placeholders such as {invoice_number}; formatting and attribute access are not supported.",
        ) from exc


def validate_edit(base: dict, proposed: dict) -> dict:
    """Copy only supported edits, then reject any change to the engine's fixed contract."""
    expected = deepcopy(base)
    baseline = sample_policy()
    try:
        for key, maximum in (("name", 200), ("notice", 500)):
            expected[key] = _text(proposed[key], key.capitalize(), maximum)
        requirements = proposed["requirements"]
        if not isinstance(requirements, list) or not 2 <= len(requirements) <= MAX_REQUIREMENTS:
            raise Unsupported(
                "INVALID_CHECKLIST",
                f"Use the two core checks and up to {MAX_REQUIREMENTS - 2} additional rules.",
            )
        keys = set()
        validated = []
        for item in requirements:
            key = item["key"]
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,59}", key) or key in keys:
                raise Unsupported(
                    "INVALID_RULE_KEY", "Each rule needs a unique identifier of at most 60 characters."
                )
            keys.add(key)
            roles = item["depends_on_roles"]
            if (
                not isinstance(roles, list)
                or not roles
                or any(r not in {"invoice", "delivery_receipt"} for r in roles)
                or len(set(roles)) != len(roles)
            ):
                raise Unsupported(
                    "INVALID_RULE_SCOPE", "Choose invoice, delivery receipts or both for each rule."
                )
            core = next((r for r in baseline["requirements"] if r["key"] == key), None)
            if core and roles != core["depends_on_roles"]:
                raise Unsupported("FIXED_RULE_SCOPE", "The core checks keep their document scope.")
            validated.append(
                {
                    "key": key,
                    "label": _text(item["label"], "Rule title", 200),
                    "description": _text(item["description"], "Review criteria", 2000),
                    "depends_on_roles": roles,
                }
            )
        if not CORE_KEYS <= keys:
            raise Unsupported(
                "CORE_CHECK_REQUIRED", "Keep the invoice calculation and delivery coverage checks."
            )
        expected["requirements"] = validated
        for key, template in base["templates"].items():
            edited = proposed["templates"][key]
            expected["templates"][key]["label"] = _text(edited["label"], "Template title", 200)
            text = _text(edited["text"], "Request wording", 2400)
            required = _slots(baseline["templates"][key]["text"])
            if _slots(text) != required:
                raise Unsupported(
                    "INVALID_TEMPLATE",
                    f"Keep these placeholders in {template['label']}: "
                    + ", ".join("{" + f + "}" for f in sorted(required)),
                )
            expected["templates"][key]["text"] = text
        for key, rule in baseline["replacement_rules"].items():
            fields = proposed["replacement_rules"][key]["may_change"]
            if (
                not isinstance(fields, list)
                or any(not isinstance(f, str) for f in fields)
                or len(set(fields)) != len(fields)
                or not set(fields) <= set(correction_fields(key, rule))
            ):
                raise Unsupported("INVALID_REPLACEMENT", "Only the listed correction fields are supported.")
            expected["replacement_rules"][key]["may_change"] = fields
        for kind, allowed in baseline["task_decisions"].items():
            choices = proposed["task_decisions"][kind]
            if (
                not isinstance(choices, list)
                or any(not isinstance(c, str) for c in choices)
                or len(set(choices)) != len(choices)
                or not set(choices) <= set(allowed)
                or "keep_on_hold" not in choices
            ):
                raise Unsupported(
                    "INVALID_DECISIONS",
                    "Choose supported decisions and keep ‘Keep the case on hold’ available for every task.",
                )
            expected["task_decisions"][kind] = choices
        for key, (section, label, _, low, high, _) in SETTING_FIELDS.items():
            raw = proposed[section][key]
            if isinstance(raw, bool):
                raise ValueError
            value = Decimal(str(raw))
            if not value.is_finite() or value < Decimal(str(low)) or value > Decimal(str(high)):
                raise Unsupported("INVALID_LIMIT", f"{label} must be between {low} and {high}.")
            if key == "case_budget_usd":
                if value != value.quantize(Decimal("0.01")):
                    raise Unsupported("INVALID_LIMIT", "Use at most two decimal places for the case budget.")
            elif value != value.to_integral_value():
                raise Unsupported("INVALID_LIMIT", f"{label} must be a whole number.")
            expected[section][key] = raw
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError) as exc:
        raise Unsupported(
            "INVALID_POLICY",
            "The policy is incomplete or contains an invalid value. Reload the latest version and try again.",
        ) from exc
    if expected != proposed:
        raise Unsupported(
            "FIXED_POLICY_RULE",
            "Core calculations, source identity, agent authority and required human review remain enforced. Use the supported policy fields.",
        )
    if expected == base:
        raise Unsupported("NO_POLICY_CHANGES", "Change at least one setting before publishing a new version.")
    for key, (section, _, _, _, _, _) in SETTING_FIELDS.items():
        expected[section][key] = (
            format(Decimal(str(expected[section][key])), ".2f")
            if key == "case_budget_usd"
            else int(expected[section][key])
        )
    return expected


def publish(session, actor, base_id, proposed: dict, reason: str) -> PolicyVersion:
    # Serialise publication within the organisation, including two different request keys.
    session.execute(
        select(OrgControl).where(OrgControl.org_id == actor.org_id).with_for_update()
    ).scalar_one()
    base = session.get(PolicyVersion, base_id)
    if not base:
        raise NotFound("POLICY_NOT_FOUND", "Policy version not found.")
    latest = (
        session.execute(
            select(PolicyVersion)
            .where(PolicyVersion.key == base.key, PolicyVersion.status == "published")
            .order_by(PolicyVersion.version.desc())
        )
        .scalars()
        .first()
    )
    if latest is None or latest.id != base.id:
        raise Conflict(
            "POLICY_CHANGED",
            "A newer policy was published while you were editing. Your draft is kept; compare it with the latest version before publishing.",
        )
    definition = validate_edit(definition_for(base), proposed)
    definition["version"] = base.version + 1
    definition["runtime_limits_version"] = 1
    policy = PolicyVersion(
        org_id=actor.org_id,
        key=base.key,
        version=definition["version"],
        name=definition["name"],
        status="published",
        definition=definition,
        published_at=utcnow(),
        published_by=actor.user_id,
    )
    session.add(policy)
    session.flush()
    record(
        session,
        None,
        "PolicyPublished",
        actor,
        f"Published {policy.name} v{policy.version}",
        reason=reason,
        payload={
            "policy_id": str(policy.id),
            "previous_policy_id": str(base.id),
            "version": policy.version,
            "changed_sections": [key for key in proposed if proposed[key] != definition_for(base).get(key)],
        },
    )
    return policy


def apply_version(session, case, actor, policy_id, reason: str) -> None:
    """Explicitly re-evaluate a case; preserve old requests, decisions and frozen exports."""
    from .casework import apply_checks, questions_of, reopen_if_complete
    from .history import bump
    from .models import HumanTask, InfoRequest, Question, RequestItem

    policy = session.get(PolicyVersion, policy_id)
    old = session.get(PolicyVersion, case.policy_id)
    if not policy or policy.key != old.key:
        raise NotFound("POLICY_NOT_FOUND", "Policy version not found for this checklist.")
    if policy.status != "published" or policy.version <= old.version:
        raise Conflict("NEWER_POLICY_REQUIRED", "Choose a newer published version.")
    if case.lifecycle == "archived" or case.execution == "paused":
        raise Conflict("CASE_NOT_ACTIVE", "Resume or reopen the case before applying a new policy.")
    previous_id = str(case.policy_id)
    reopen_if_complete(session, case, actor, "Policy version updated")
    case.policy_id = policy.id
    case.policy_review = {}
    questions = questions_of(session, case.id)
    for rule in policy.definition["requirements"]:
        question = questions.get(rule["key"])
        if question:
            question.label = rule["label"]
            question.state = "open"
            question.resolved_at = question.resolved_revision = question.resolved_by = None
            question.authorised_template = None
        else:
            session.add(
                Question(
                    org_id=case.org_id, case_id=case.id, requirement_key=rule["key"], label=rule["label"]
                )
            )
    for request in session.execute(
        select(InfoRequest).where(
            InfoRequest.case_id == case.id, InfoRequest.state.in_(("draft", "proposed", "issued"))
        )
    ).scalars():
        request.state = "superseded"
        for item in session.execute(
            select(RequestItem).where(
                RequestItem.request_id == request.id, RequestItem.status.in_(("outstanding", "progress"))
            )
        ).scalars():
            item.status = "closed"
            item.progress_note = "Replaced by a review under the updated policy."
    for task in session.execute(
        select(HumanTask).where(
            HumanTask.case_id == case.id,
            HumanTask.kind.in_(("policy_review", "no_response", "evidence_problem")),
            HumanTask.state.in_(("pending", "claimed")),
        )
    ).scalars():
        active_keys = {r["key"] for r in policy.definition["requirements"]}
        if task.kind in {"policy_review", "no_response"} or (
            task.requirement_keys and not active_keys.intersection(task.requirement_keys)
        ):
            task.state = "superseded"
    session.flush()
    bump(case)
    apply_checks(session, case, actor, resolve=False)
    record(
        session,
        case,
        "CasePolicyUpdated",
        actor,
        f"Applied {policy.name} v{policy.version}",
        reason=reason,
        payload={"previous_policy_id": previous_id, "policy_id": str(policy.id)},
    )
