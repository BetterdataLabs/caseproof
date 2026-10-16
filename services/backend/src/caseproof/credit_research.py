"""Public company research configuration and report contract; separate from lending authority."""

from copy import deepcopy
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from .config import get_settings
from .history import record, utcnow

METHOD = "public-company-research/1"
LIMITATION = (
    "Public-source credit research for bank review, not a credit rating or a lending decision. "
    "Missing information and no adverse search results do not establish creditworthiness. "
    "Confirm the entity, financial statements and repayment capacity before relying on this report."
)
DIMENSIONS = {
    "identity": "Company identity and ownership",
    "repayment": "Cash flow and repayment capacity",
    "financial_strength": "Liquidity, debt and capital",
    "conduct": "Legal, regulatory and payment concerns",
    "sector": "Industry and country conditions",
    "concentration": "Customers, suppliers and operating dependencies",
}
MISSING = [
    "Current financial statements and management accounts, with the reporting period and currency.",
    "Cash-flow forecasts, debt maturities, repayment history and bank references.",
    "Verified legal identity, ownership and the bank's required registry and sanctions checks.",
    "Facility terms, repayment source, security and the bank's own credit policy assessment.",
]


class ResearchOptions(BaseModel):
    enabled: bool = False
    target: Literal["buyer", "seller"] = "buyer"
    country: str = Field(default="", max_length=80)
    registration_number: str = Field(default="", max_length=80)


def allocate_budget(case, actor, session) -> None:
    """Add the configured research allowance once, including for older failed requests."""
    report = case.credit_research or {}
    if not report.get("enabled"):
        return
    allowance = get_settings().research_budget_usd
    previous = Decimal(report.get("budget_allowance_usd", "0"))
    additional = max(Decimal("0"), allowance - previous)
    if not additional:
        return
    case.budget_usd = Decimal(case.budget_usd) + additional
    case.credit_research = {**report, "budget_allowance_usd": str(allowance)}
    record(
        session,
        case,
        "CreditResearchBudgetAllocated",
        actor,
        f"Added USD {additional:.2f} to the case budget for company research",
        payload={
            "additional_usd": str(additional),
            "research_allowance_usd": str(allowance),
            "case_budget_usd": str(case.budget_usd),
        },
    )


def configure(case, actor, session, options: ResearchOptions) -> None:
    if not options.enabled:
        return
    from .errors import Unsupported

    country = options.country.strip()
    if not country or any(ord(c) < 32 for c in country + options.registration_number):
        raise Unsupported("COMPANY_COUNTRY_REQUIRED", "Enter the company's country of registration.")
    previous_allowance = (case.credit_research or {}).get("budget_allowance_usd", "0")
    case.credit_research = {
        **options.model_dump(),
        "country": country,
        "registration_number": options.registration_number.strip(),
        "status": "pending",
        "method": METHOD,
        "requested_by": actor.name,
        "requested_at": utcnow().isoformat(),
        "searches": [],
        "limitation": LIMITATION,
        "budget_allowance_usd": previous_allowance,
    }
    allocate_budget(case, actor, session)
    record(
        session,
        case,
        "CreditResearchRequested",
        actor,
        f"Public company research requested for the {options.target}",
    )


def public_report(value: dict | None) -> dict:
    return deepcopy(value or {"enabled": False})
