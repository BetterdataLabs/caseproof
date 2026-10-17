"""Deterministic domain checks: decimal arithmetic, references, delivery-event identity and dispute conditions.

These are pure functions over validated facts. Gemini never computes a total or a quantity; the agent asks
for these results through `run_checks` and the completion service recomputes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .pdfdocs import money_value

CHECKS_VERSION = "checks/1.0"


@dataclass
class VersionView:
    id: str
    label: str
    role: str
    number: str
    version_no: int | None
    replaces_version_no: int | None
    state: str
    is_active: bool
    duplicate_of: str | None
    coverage: str
    facts: dict[str, str]
    reject_code: str | None = None
    reject_detail: str = ""


@dataclass
class ClaimView:
    id: str
    requirement_key: str
    status: str
    conditions: dict[str, Any]


@dataclass
class PartyView:
    seller: str
    buyer: str
    receipt_issuers: list[str]
    invoice_reference: str


@dataclass
class CheckResult:
    key: str
    result: str  # pass | fail | missing | blocked
    reason_code: str
    detail: str
    evidence_refs: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    satisfied_claims: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "result": self.result,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "evidence_refs": self.evidence_refs,
            "metrics": self.metrics,
        }


def _fmt(amount: Decimal) -> str:
    return f"SGD {amount:,.2f}"


def _qty(text: str) -> Decimal:
    return Decimal(text)


def active_invoice(versions: list[VersionView]) -> VersionView | None:
    for v in versions:
        if v.role == "invoice" and v.is_active and v.state == "ready":
            return v
    return None


def evaluate_invoice_total(parties: PartyView, versions: list[VersionView]) -> CheckResult:
    key = "invoice_total"
    invoice = active_invoice(versions)
    invoices = [v for v in versions if v.role == "invoice"]
    blocked = [v for v in invoices if v.state == "rejected" and v.coverage == "blocking"]
    if invoice is None:
        if blocked:
            latest = blocked[-1]
            return CheckResult(
                key,
                "missing",
                "NO_SUPPORTED_INVOICE",
                f"{latest.label} could not be used: {latest.reject_detail}",
                [v.id for v in blocked],
                {"rejection": latest.reject_detail, "rejected_label": latest.label},
            )
        return CheckResult(key, "missing", "NO_INVOICE", "No invoice has been received.")
    f = invoice.facts
    refs = [invoice.id]
    if f.get("seller") != parties.seller or f.get("buyer") != parties.buyer:
        return CheckResult(
            key,
            "fail",
            "PARTY_MISMATCH",
            f"{invoice.label} names seller '{f.get('seller')}' and buyer '{f.get('buyer')}', which do not "
            f"match the case parties.",
            refs,
        )
    if f.get("invoice_number") != parties.invoice_reference:
        return CheckResult(
            key,
            "fail",
            "REFERENCE_MISMATCH",
            f"{invoice.label} is invoice {f.get('invoice_number')}, not {parties.invoice_reference}.",
            refs,
        )
    quantity = _qty(f["quantity"])
    unit_price = money_value(f["unit_price"])
    stated = money_value(f["total_amount"])
    expected = (quantity * unit_price).quantize(Decimal("0.01"))
    metrics = {
        "quantity": str(quantity),
        "unit": f["unit"],
        "unit_price": str(unit_price),
        "stated_total": str(stated),
        "expected_total": str(expected),
        "difference": str(stated - expected),
        "invoice_version": invoice.version_no,
        "invoice_label": invoice.label,
    }
    later_rejected = [v for v in blocked if (v.version_no or 0) > (invoice.version_no or 0)]
    if stated != expected:
        if later_rejected:
            latest = later_rejected[-1]
            metrics["rejection"] = latest.reject_detail
            metrics["rejection_code"] = latest.reject_code
            metrics["rejected_label"] = latest.label
            return CheckResult(
                key,
                "fail",
                "REPLACEMENT_REJECTED",
                f"{invoice.label} states {_fmt(stated)} but {quantity} {f['unit']} × {_fmt(unit_price)} = "
                f"{_fmt(expected)}. Replacement {latest.label} was not accepted: {latest.reject_detail}",
                refs + [latest.id],
                metrics,
            )
        return CheckResult(
            key,
            "fail",
            "TOTAL_MISMATCH",
            f"{invoice.label} states {_fmt(stated)} but {quantity} {f['unit']} × {_fmt(unit_price)} = "
            f"{_fmt(expected)} (difference {_fmt(stated - expected)}).",
            refs,
            metrics,
        )
    if later_rejected:
        latest = later_rejected[-1]
        return CheckResult(
            key,
            "blocked",
            "REPLACEMENT_REJECTED",
            f"{invoice.label} is arithmetically correct, but a later version {latest.label} was not accepted "
            f"({latest.reject_detail}). The conflict must be addressed.",
            refs + [latest.id],
            metrics,
        )
    return CheckResult(
        key,
        "pass",
        "TOTAL_AGREES",
        f"{invoice.label}: {quantity} {f['unit']} × {_fmt(unit_price)} = {_fmt(expected)}, as stated.",
        refs,
        metrics,
    )


def evaluate_delivery(
    parties: PartyView, versions: list[VersionView], claims: list[ClaimView]
) -> CheckResult:
    key = "delivery_receipts"
    invoice = active_invoice(versions)
    if invoice is None:
        return CheckResult(
            key, "blocked", "INVOICE_REQUIRED", "Delivery cannot be checked without a supported invoice."
        )
    inv = invoice.facts
    invoiced = _qty(inv["quantity"])
    receipts = [v for v in versions if v.role == "delivery_receipt"]
    active = [v for v in receipts if v.is_active and v.state == "ready" and not v.duplicate_of]
    copies = [v for v in receipts if v.duplicate_of]
    rejected = [v for v in receipts if v.state == "rejected" and v.coverage == "blocking"]
    refs = [invoice.id] + [v.id for v in active]
    metrics: dict[str, Any] = {
        "invoiced_quantity": str(invoiced),
        "unit": inv["unit"],
        "item": inv["item"],
        "invoice_number": inv["invoice_number"],
        "copies_ignored": [c.label for c in copies],
    }

    mismatched: list[str] = []
    counted: list[VersionView] = []
    for r in active:
        f = r.facts
        problems = []
        if f.get("invoice_ref") != inv["invoice_number"]:
            problems.append(f"references {f.get('invoice_ref')} instead of {inv['invoice_number']}")
        if f.get("item") != inv["item"]:
            problems.append(f"goods '{f.get('item')}' differ from the invoice")
        if f.get("unit") != inv["unit"]:
            problems.append(f"unit '{f.get('unit')}' differs from '{inv['unit']}'")
        if f.get("supplier") != parties.seller:
            problems.append(f"supplier '{f.get('supplier')}' is not the seller")
        if f.get("issued_by") not in parties.receipt_issuers:
            problems.append(f"issuer '{f.get('issued_by')}' is not a permitted receipt source")
        if problems:
            mismatched.append(f"{r.label} ({r.number}) " + "; ".join(problems))
        else:
            counted.append(r)

    cumulative = [r for r in counted if r.facts.get("basis", "").lower().startswith("cumulative")]
    if cumulative:
        labels = ", ".join(f"{r.label} ({r.number})" for r in cumulative)
        metrics["receipt_label"] = labels
        return CheckResult(
            key,
            "blocked",
            "CUMULATIVE_RECEIPT",
            f"{labels} states a cumulative quantity to date. Quantities cannot be added without knowing "
            f"which deliveries it includes; a corrected receipt or a source-backed disposition is required.",
            refs,
            metrics,
        )

    events: dict[str, list[VersionView]] = {}
    for r in counted:
        events.setdefault(r.facts.get("delivery_ref", "?"), []).append(r)
    total = Decimal(0)
    event_rows = []
    for ref, items in sorted(events.items()):
        quantities = {_qty(i.facts["quantity"]) for i in items}
        if len(quantities) > 1:
            labels = ", ".join(f"{i.label} ({i.number}: {i.facts['quantity']})" for i in items)
            metrics["receipt_label"] = labels
            return CheckResult(
                key,
                "blocked",
                "CONFLICTING_DELIVERY_EVENT",
                f"Delivery {ref} is described by more than one receipt with different quantities ({labels}). "
                f"Without an explicit replacement, the quantities are not added.",
                refs,
                metrics,
            )
        quantity = quantities.pop()
        total += quantity
        event_rows.append(
            {
                "delivery_ref": ref,
                "quantity": str(quantity),
                "receipts": [i.label for i in items],
                "received_at": items[0].facts.get("received_at", ""),
            }
        )
    metrics.update(
        {
            "received_quantity": str(total),
            "outstanding_quantity": str(max(invoiced - total, Decimal(0))),
            "events": event_rows,
            "known_deliveries": ", ".join(sorted(events)) or "none",
        }
    )

    if mismatched:
        return CheckResult(
            key,
            "fail",
            "RECEIPT_MISMATCH",
            "Receipt cannot count toward the invoice: " + " | ".join(mismatched),
            refs,
            metrics,
        )

    # Retained disputes: the recorded conditions must be met by the current evidence.
    satisfied: list[str] = []
    for claim in claims:
        if claim.requirement_key != key or claim.status != "retained":
            continue
        c = claim.conditions
        target = [r for r in counted if r.number == c.get("receipt_number")]
        if not target or (target[0].version_no or 0) <= int(c.get("disputed_version", 1)):
            return CheckResult(
                key,
                "blocked",
                "DISPUTE_RETAINED",
                f"A retained dispute says delivery {c.get('delivery_ref')} had {c.get('claimed_quantity')} "
                f"{inv['unit']}, not what {c.get('receipt_number')} v{c.get('disputed_version', 1)} states. "
                f"Awaiting a corrected receipt that explicitly replaces it.",
                refs,
                metrics,
            )
        corrected = target[0]
        if (
            corrected.facts.get("delivery_ref") != c.get("delivery_ref")
            or _qty(corrected.facts["quantity"]) != _qty(str(c.get("claimed_quantity")))
            or corrected.replaces_version_no != int(c.get("disputed_version", 1))
        ):
            return CheckResult(
                key,
                "blocked",
                "CONDITIONS_NOT_MET",
                f"{corrected.label} ({corrected.number} v{corrected.version_no}) states "
                f"{corrected.facts['quantity']} {inv['unit']} for {corrected.facts.get('delivery_ref')}, which "
                f"does not match the reviewer's recorded condition of {c.get('claimed_quantity')} "
                f"{inv['unit']} for {c.get('delivery_ref')}. This returns to the reviewer.",
                refs + [corrected.id],
                metrics,
            )
        satisfied.append(claim.id)

    if total < invoiced:
        detail = (
            f"Distinct deliveries cover {total} of {invoiced} {inv['unit']} "
            f"({', '.join(sorted(events)) or 'no deliveries'}); {invoiced - total} {inv['unit']} have no receipt."
        )
        if copies:
            detail += f" {len(copies)} duplicate cop{'y' if len(copies) == 1 else 'ies'} counted once."
        if rejected:
            detail += f" {', '.join(r.label for r in rejected)} could not be used."
        return CheckResult(key, "missing", "RECEIPT_SHORTFALL", detail, refs, metrics, satisfied)
    if total > invoiced:
        return CheckResult(
            key,
            "fail",
            "OVER_RECEIPT",
            f"Receipts cover {total} {inv['unit']}, more than the {invoiced} invoiced.",
            refs,
            metrics,
        )
    detail = f"Distinct deliveries {', '.join(sorted(events))} cover all {invoiced} {inv['unit']}."
    if copies:
        detail += f" {len(copies)} duplicate cop{'y' if len(copies) == 1 else 'ies'} counted once."
    return CheckResult(key, "pass", "FULL_RECEIPT", detail, refs, metrics, satisfied)


def evaluate(
    parties: PartyView, versions: list[VersionView], claims: list[ClaimView]
) -> dict[str, CheckResult]:
    return {
        "invoice_total": evaluate_invoice_total(parties, versions),
        "delivery_receipts": evaluate_delivery(parties, versions, claims),
    }
