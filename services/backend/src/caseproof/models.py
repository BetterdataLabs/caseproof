"""Authoritative records. PostgreSQL owns case state, decisions, jobs and history."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB, uuid.UUID: UUID(as_uuid=True)}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False, index=True)


# identity (global, read-only to runtime)


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _ts()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    subject: Mapped[str] = mapped_column(
        String(200), unique=True
    )  # stable identity subject (IAP sub or dev:)
    email: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = _ts()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()


# policy and controls


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("org_id", "key", "version"), UniqueConstraint("org_id", "id"))
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    key: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))  # draft | published | retired
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts()


class OrgControl(Base):
    """Organisation automation controls (emergency stop, fault injection). Versioned by revision."""

    __tablename__ = "org_controls"
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    model_fault: Mapped[str | None] = mapped_column(String(40))  # demo fault injection: timeout | quota
    model_fault_remaining: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = _ts()
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text, default="")


# cases


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("org_id", "id"),
        UniqueConstraint("org_id", "reference"),
        ForeignKeyConstraint(["org_id", "policy_id"], ["policy_versions.org_id", "policy_versions.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    reference: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    product: Mapped[str] = mapped_column(String(60), default="sales_invoice_financing")
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    scenario_key: Mapped[str] = mapped_column(String(80))  # fixture catalog entry (not expected outcomes)
    seller: Mapped[dict[str, Any]] = mapped_column(JSONB)
    buyer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    permitted_receipt_issuers: Mapped[list[Any]] = mapped_column(JSONB)
    invoice_reference: Mapped[str] = mapped_column(String(60))
    document_checks: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    credit_research: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    policy_review: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    facility_reference: Mapped[str] = mapped_column(String(60), default="")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    vendor_contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    lifecycle: Mapped[str] = mapped_column(String(20), default="open")  # open | complete | archived
    execution: Mapped[str] = mapped_column(String(30), default="idle")
    # queued | running | waiting_evidence | waiting_decision | paused | idle
    automation_mode: Mapped[str] = mapped_column(
        String(20), default="autonomous"
    )  # off | shadow | autonomous
    paused_reason: Mapped[str | None] = mapped_column(String(60))
    next_action: Mapped[str] = mapped_column(Text, default="")
    next_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wakeups_used: Mapped[int] = mapped_column(Integer, default=0)
    wakeup_extension: Mapped[int] = mapped_column(Integer, default=0)
    request_rounds_used: Mapped[int] = mapped_column(Integer, default=0)
    extra_rounds_authorised: Mapped[int] = mapped_column(Integer, default=0)
    budget_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    cost_reserved_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    cost_actual_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    clock_offset_s: Mapped[int] = mapped_column(BigInteger, default=0)  # demo clock, simulation only
    current_export_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class Question(Base):
    """One checklist requirement on one case. Separate questions stay separate."""

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("case_id", "requirement_key"),
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    requirement_key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(30), default="open")
    # open | waiting_evidence | waiting_decision | resolved
    check_result: Mapped[str] = mapped_column(
        String(30), default="pending"
    )  # pass | fail | missing | blocked | pending
    reason_code: Mapped[str] = mapped_column(String(60), default="NOT_CHECKED")
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)  # document version ids
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_revision: Mapped[int | None] = mapped_column(Integer)
    resolved_by: Mapped[str | None] = mapped_column(String(60))
    checked_revision: Mapped[int | None] = mapped_column(Integer)
    authorised_template: Mapped[str | None] = mapped_column(
        String(60)
    )  # set by a reviewer's authorise decision
    updated_at: Mapped[datetime] = _ts()


# evidence


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("case_id", "role", "number"),
        UniqueConstraint("org_id", "id"),
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(
        String(40)
    )  # invoice | delivery_receipt | written_message | status_update
    number: Mapped[str] = mapped_column(String(80))  # INV-101, R1, MSG-1 ...
    title: Mapped[str] = mapped_column(String(200))
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts()


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
        ForeignKeyConstraint(["org_id", "document_id"], ["documents.org_id", "documents.id"]),
        UniqueConstraint("org_id", "id"),
        Index("ix_docver_case", "case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    label: Mapped[str] = mapped_column(String(40))  # S1, S2 ... stable per case for citations
    sequence: Mapped[int] = mapped_column(Integer)
    source_role: Mapped[str] = mapped_column(String(40))
    declared_issuer: Mapped[str] = mapped_column(String(200), default="")  # catalog source role assumption
    version_no: Mapped[int | None] = mapped_column(Integer)
    replaces_version_no: Mapped[int | None] = mapped_column(Integer)
    business_event_ref: Mapped[str | None] = mapped_column(String(80))  # delivery reference, e.g. D1
    state: Mapped[str] = mapped_column(String(20), default="received")
    # received | validating | ready | rejected | withdrawn | superseded
    reject_code: Mapped[str | None] = mapped_column(String(60))
    reject_detail: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    object_key: Mapped[str | None] = mapped_column(String(300))
    object_generation: Mapped[str | None] = mapped_column(String(80))
    sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    mime: Mapped[str | None] = mapped_column(String(80))
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_content: Mapped[str | None] = mapped_column(Text)  # extracted text or the written message
    structured: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # structured reply fields
    attributed_to: Mapped[str | None] = mapped_column(String(200))  # written message attribution (not proof)
    coverage: Mapped[str] = mapped_column(String(30), default="pending")
    # pending | processed | needs_review | reviewed | not_required
    covered_by_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    received_via: Mapped[str] = mapped_column(String(30))  # initial | reply | manual
    reply_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    fixture_key: Mapped[str | None] = mapped_column(String(80))
    parser_version: Mapped[str | None] = mapped_column(String(40))
    visual_review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    received_revision: Mapped[int] = mapped_column(Integer)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()


class Fact(Base):
    """A typed field value verified against the original's text (quote must occur in the source)."""

    __tablename__ = "facts"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "version_id"], ["document_versions.org_id", "document_versions.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    field: Mapped[str] = mapped_column(String(60))
    value: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer, default=1)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Observation(Base):
    """Model-produced, schema-validated observation with exact quotations. Not a validated fact."""

    __tablename__ = "observations"
    __table_args__ = (ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    compared_version_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    relation: Mapped[str] = mapped_column(
        String(40)
    )  # contradicts | consistent | new_information | unrelated | unclear
    affected_requirement: Mapped[str | None] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(80))
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    invalid_reason: Mapped[str | None] = mapped_column(String(80))
    case_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts()


class MaterialClaim(Base):
    """A disputed statement retained by a human decision, with its acceptance conditions."""

    __tablename__ = "material_claims"
    __table_args__ = (ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    requirement_key: Mapped[str] = mapped_column(String(60))
    source_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    statement: Mapped[str] = mapped_column(Text)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="retained")  # retained | satisfied | superseded
    satisfied_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts()


# requests and the simulated exchange


class InfoRequest(Base):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("case_id", "intent_key", "round", name="uq_request_intent_round"),
        UniqueConstraint("org_id", "id"),
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    intent_key: Mapped[str] = mapped_column(String(80))
    round: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft | issued | answered | closed | proposed
    recipient: Mapped[str] = mapped_column(String(200))  # fixed case recipient, never model-supplied
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    authorised_by_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    prepared_revision: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(40), default="agent")
    created_at: Mapped[datetime] = _ts()


class RequestItem(Base):
    __tablename__ = "request_items"
    __table_args__ = (ForeignKeyConstraint(["org_id", "request_id"], ["requests.org_id", "requests.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    template_id: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), default="outstanding"
    )  # outstanding | progress | answered
    progress_note: Mapped[str] = mapped_column(Text, default="")


class Reply(Base):
    """Documents or a written response received through the portal, bank workspace or demo inbox."""

    __tablename__ = "replies"
    __table_args__ = (
        UniqueConstraint("case_id", "dedupe_key", name="uq_reply_dedupe"),
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(30))  # status_update | document | written_message | withdrawal
    staged_key: Mapped[str | None] = mapped_column(String(80))
    dedupe_key: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(200))
    version_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    case_revision: Mapped[int] = mapped_column(Integer)
    processed_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts()


# human tasks and decisions


class HumanTask(Base):
    __tablename__ = "human_tasks"
    __table_args__ = (
        UniqueConstraint("org_id", "id"),
        ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),
        Index("ix_task_open", "org_id", "state"),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    # message_review | dispute | no_response | service_failure | budget_exhausted | evidence_problem
    state: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | claimed | decided | superseded
    title: Mapped[str] = mapped_column(String(300))
    question: Mapped[str] = mapped_column(Text)  # the exact question for the person
    why_stopped: Mapped[str] = mapped_column(Text)
    proposed_action: Mapped[str] = mapped_column(Text, default="")
    requirement_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    source_version_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    observation_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    passages: Mapped[list[Any]] = mapped_column(JSONB, default=list)  # [{label, quote, version_id}]
    allowed_decisions: Mapped[list[Any]] = mapped_column(JSONB)
    required_role: Mapped[str] = mapped_column(String(40), default="reviewer")
    opened_by: Mapped[str] = mapped_column(String(40), default="agent")
    created_revision: Mapped[int] = mapped_column(Integer)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = _ts()


Index(
    "uq_task_open_dedupe",
    HumanTask.case_id,
    HumanTask.dedupe_key,
    unique=True,
    postgresql_where=text("state IN ('pending','claimed')"),
)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (ForeignKeyConstraint(["org_id", "task_id"], ["human_tasks.org_id", "human_tasks.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True
    )  # one current decision per task
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision_type: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    covered_version_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    case_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts()


# execution


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="agent")  # agent | export
    trigger: Mapped[str] = mapped_column(String(60))
    trigger_detail: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(
        String(20), default="queued"
    )  # queued | leased | done | failed | cancelled
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_revision: Mapped[int] = mapped_column(Integer)
    next_eligible_at: Mapped[datetime] = _ts()
    deferrals: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    export_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("uq_job_queued_per_case", Job.case_id, Job.kind, unique=True, postgresql_where=text("state = 'queued'"))
Index(
    "uq_job_leased_per_case",
    Job.case_id,
    unique=True,
    postgresql_where=text("state = 'leased' AND kind = 'agent'"),
)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # ids only, never source content
    created_at: Mapped[datetime] = _ts()
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


Index("ix_outbox_pending", Outbox.created_at, postgresql_where=text("dispatched_at IS NULL"))


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    trigger: Mapped[str] = mapped_column(String(60))
    mode: Mapped[str] = mapped_column(String(20))
    controller: Mapped[str] = mapped_column(String(40))  # adk-gemini | rule-controller
    model: Mapped[str] = mapped_column(String(80), default="")
    input_revision: Mapped[int] = mapped_column(Integer)
    final_revision: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(40), default="running")
    # running | waiting | human_task | completed | paused | stale | failed | no_action
    stop_reason: Mapped[str] = mapped_column(String(80), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentAction(Base):
    """One tool invocation by the agent: arguments (sanitised), result code and a short reason."""

    __tablename__ = "agent_actions"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(40))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result_code: Mapped[str] = mapped_column(String(60))
    result_summary: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    shadow: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _ts()


class ProviderCall(Base):
    __tablename__ = "provider_calls"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(40))  # agent_step | compare_statements
    model: Mapped[str] = mapped_column(String(80))
    location: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))  # reserved | ok | error | timeout
    error_code: Mapped[str | None] = mapped_column(String(60))
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    thinking_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    usage_day: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = _ts()


# history, commands, exports


class AuditEvent(Base):
    """Append-only to application roles (UPDATE/DELETE revoked in the migration)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_case", "case_id", "id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=new_id, unique=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    case_revision: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(60))
    actor_type: Mapped[str] = mapped_column(String(30))  # person | agent | policy | system | simulation
    actor_id: Mapped[str] = mapped_column(String(80))
    actor_name: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = _ts()


class CommandReceipt(Base):
    """Idempotency: a key is bound to organisation, actor, route and payload hash."""

    __tablename__ = "command_receipts"
    __table_args__ = (UniqueConstraint("org_id", "actor_id", "idempotency_key"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    route: Mapped[str] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts()


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (ForeignKeyConstraint(["org_id", "case_id"], ["cases.org_id", "cases.id"]),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = _org()
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    export_ref: Mapped[str] = mapped_column(String(40), unique=True)
    case_revision: Mapped[int] = mapped_column(Integer)
    policy_label: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(
        String(20), default="preparing"
    )  # preparing | ready | failed | superseded
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    pdf_key: Mapped[str | None] = mapped_column(String(300))
    json_key: Mapped[str | None] = mapped_column(String(300))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_reason: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _ts()
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PurgeRecord(Base):
    """Retention ledger: reapplied after a restore so purged cases are never served again."""

    __tablename__ = "purge_records"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reference: Mapped[str] = mapped_column(String(40))
    purged_at: Mapped[datetime] = _ts()
    reason: Mapped[str] = mapped_column(Text)


ORG_SCOPED_TABLES = [
    "policy_versions",
    "org_controls",
    "cases",
    "questions",
    "documents",
    "document_versions",
    "facts",
    "observations",
    "material_claims",
    "requests",
    "request_items",
    "replies",
    "human_tasks",
    "decisions",
    "jobs",
    "outbox",
    "agent_runs",
    "agent_actions",
    "provider_calls",
    "audit_events",
    "command_receipts",
    "exports",
]
