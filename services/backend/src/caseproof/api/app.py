"""FastAPI command API (/v1). Validates identity, roles, typed commands and current revisions.

No long-running model work happens inside a browser request: commands record state and outbox obligations,
return 202 for accepted asynchronous work, and the dispatcher delivers jobs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .. import catalog, vendor
from ..actors import (
    ROLE_ADMIN,
    ROLE_AUDITOR,
    ROLE_REVIEWER,
    ROLE_SIMULATION,
    ROLE_SUPERVISOR,
    ROLE_VENDOR,
    Actor,
)
from ..casework import apply_checks, create_case, org_controls, settle_execution, try_complete
from ..config import get_settings
from ..credit_research import ResearchOptions
from ..credit_research import allocate_budget as allocate_research_budget
from ..db import global_session, org_session
from ..document_checks import configure_checks
from ..document_content import EXTENSIONS, identify_format, image_preview
from ..errors import Conflict, DomainError, Forbidden, NotFound, StaleRevision, Throttled, Unsupported
from ..history import bump, lock_case, record, utcnow
from ..identity import (
    DEMO_COOKIE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    SessionData,
    access_code_matches,
    actor_for,
    csrf_token,
    demo_cookie_valid,
    demo_gate_required,
    dev_sign_in_allowed,
    memberships_for,
    new_session,
    sign_demo_gate,
    sign_session,
)
from ..intake import MAX_FILE_BYTES, MAX_FILES, MAX_UPLOAD_BYTES, Upload, add_input, create_uploaded_case
from ..jobs import enqueue_agent, record_pause
from ..models import (
    AgentRun,
    AuditEvent,
    Case,
    CommandReceipt,
    DocumentVersion,
    Export,
    HumanTask,
    Job,
    Membership,
    Organisation,
    PolicyVersion,
    ProviderCall,
    User,
)
from ..pdfdocs import render_preview
from ..policies import definition_for, editor_schema
from ..policies import publish as publish_policy
from ..queue import prompt_dispatch
from ..requests import advance_demo_clock, issue_request, prepare_request, receive_staged_response
from ..storage import object_store
from ..tasks import claim, decide, release
from ..views import audit_json, case_detail, etag_for, list_cases, list_research, task_inbox

log = logging.getLogger("caseproof.api")
settings = get_settings()
app = FastAPI(title="CaseProof API", version="1.0.0", docs_url="/v1/docs", openapi_url="/v1/openapi.json")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_ORIGIN = re.compile(
    r"^http://(localhost|127\.0\.0\.1)(:\d{1,5})?$"
)  # development only (forwarded ports)


# middleware


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method in MUTATING:
        is_upload = bool(
            re.fullmatch(
                r"/v1/cases/upload|/v1/cases/[^/]+/(inputs|document-checks)|/v1/vendor/cases(?:/[^/]+/inputs)?",
                request.url.path,
            )
        )
        limit = MAX_UPLOAD_BYTES if is_upload else settings.max_command_bytes
        try:
            length = int(request.headers.get("content-length") or 0)
        except ValueError:
            return _error(400, "INVALID_LENGTH", "Invalid request length.")
        if length > limit:
            return _error(
                413,
                "COMMAND_TOO_LARGE",
                "Upload limit is 20 MiB of files; other commands are limited to 32 KiB.",
            )
        origin = request.headers.get("origin")
        if (
            origin
            and origin not in settings.origins
            and not (settings.environment != "cloud" and LOCAL_ORIGIN.match(origin))
        ):
            return _error(403, "BAD_ORIGIN", "Cross-origin commands are not accepted.")
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                return _error(
                    413, "COMMAND_TOO_LARGE", "The request exceeds the upload or command size limit."
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _error(status: int, code: str, message: str, detail: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message, "detail": detail or {}}}
    )


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message, exc.detail)


# dependencies


class Ctx:
    def __init__(self, actor: Actor, session: SessionData | None, user: User, memberships: list) -> None:
        self.actor = actor
        self.session = session
        self.user = user
        self.memberships = memberships


def current(request: Request) -> Ctx:
    actor, session, user, memberships = actor_for(request)
    path = request.url.path
    if actor.workspace == "vendor" and not path.startswith(("/v1/vendor/", "/v1/session")):
        raise Forbidden(
            "VENDOR_WORKSPACE", "Use your vendor workspace to view and reply to your submissions."
        )
    if path.startswith("/v1/vendor/") and actor.workspace != "vendor":
        raise Forbidden("VENDOR_REQUIRED", "This workspace is for vendor submissions.")
    if actor.workspace == "viewer" and request.method in MUTATING and not path.startswith("/v1/session"):
        raise Forbidden("READ_ONLY", "Your viewer account can inspect information but cannot change it.")
    return Ctx(actor, session, user, memberships)


def command(
    request: Request,
    ctx: Ctx = Depends(current),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> tuple[Ctx, str]:
    if ctx.session is None or not x_csrf_token or x_csrf_token != csrf_token(ctx.session):
        raise Forbidden("CSRF", "The request is missing a valid anti-forgery token.")
    if not idempotency_key or not 8 <= len(idempotency_key) <= 120:
        raise Unsupported("IDEMPOTENCY_KEY_REQUIRED", "Every command needs an Idempotency-Key header.")
    return ctx, idempotency_key


def require(actor: Actor, *roles: str) -> None:
    if not actor.has(*roles):
        raise Forbidden("ROLE_REQUIRED", "Your role does not allow this action.", required=list(roles))


def run_command(
    ctx: Ctx, key: str, route: str, payload: dict[str, Any], fn, status: int = 200
) -> JSONResponse:
    """Idempotent command execution: the key is bound to organisation, actor, route and payload."""
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    org_id = ctx.actor.org_id
    for _ in range(2):
        try:
            with org_session(org_id) as session:
                prior = session.execute(
                    select(CommandReceipt).where(
                        CommandReceipt.org_id == org_id,
                        CommandReceipt.actor_id == ctx.actor.user_id,
                        CommandReceipt.idempotency_key == key,
                    )
                ).scalar_one_or_none()
                if prior is not None:
                    if prior.payload_hash != payload_hash or prior.route != route:
                        raise Conflict(
                            "IDEMPOTENCY_KEY_REUSED", "This key was already used for a different command."
                        )
                    return JSONResponse(
                        status_code=prior.status_code,
                        content=prior.response,
                        headers={"Idempotent-Replay": "true"},
                    )
                result = fn(session)
                body = json.loads(json.dumps(result, default=str))
                session.add(
                    CommandReceipt(
                        org_id=org_id,
                        actor_id=ctx.actor.user_id,
                        idempotency_key=key,
                        route=route,
                        payload_hash=payload_hash,
                        status_code=status,
                        response=body,
                    )
                )
            prompt_dispatch(org_id)
            return JSONResponse(status_code=status, content=body)
        except IntegrityError:
            continue  # a concurrent duplicate committed first; replay its receipt
    raise Conflict("IDEMPOTENCY_RACE", "The command could not be recorded; retry with the same key.")


def load_case(session: Session, case_id: str) -> Case:
    try:
        cid = uuid.UUID(case_id)
    except ValueError as exc:
        raise NotFound("CASE_NOT_FOUND", "Case not found.") from exc
    case = session.get(Case, cid)
    if case is None:  # row policy hides other organisations' cases: indistinguishable from missing
        raise NotFound("CASE_NOT_FOUND", "Case not found.")
    return case


# session


@app.get("/v1/health")
def health() -> dict[str, Any]:
    ok = True
    try:
        with global_session() as session:
            session.execute(select(func.now()))
    except Exception:
        ok = False
    return {
        "status": "ok" if ok else "degraded",
        "database": ok,
        "model": settings.model_name,
        "location": settings.model_location,
        "environment": settings.environment,
    }


_UNLOCK_WINDOW_S = 600
_UNLOCK_LIMIT = 8
_unlock_failures: dict[str, list[float]] = {}


def _client_addr(request: Request) -> str:
    # Set by our web proxy from the last Cloud Run hop. The API is not public.
    client = request.headers.get("x-caseproof-client", "").strip()
    if client:
        return client[:80]
    host = request.client.host if request.client else "unknown"
    return host[:80]


def _unlock_blocked(addr: str) -> bool:
    now = time.monotonic()
    recent = [stamp for stamp in _unlock_failures.get(addr, []) if now - stamp < _UNLOCK_WINDOW_S]
    _unlock_failures[addr] = recent
    return len(recent) >= _UNLOCK_LIMIT


def _remember_unlock_failure(addr: str) -> None:
    _unlock_failures.setdefault(addr, []).append(time.monotonic())


def _set_session_cookie(response: Response, data: SessionData) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(data),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "cloud",
        path="/",
    )


@app.get("/v1/demo/gate")
def demo_gate(request: Request) -> dict[str, Any]:
    required = demo_gate_required()
    return {"required": required, "unlocked": (not required) or demo_cookie_valid(request)}


class UnlockIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)


@app.post("/v1/demo/unlock")
def demo_unlock(body: UnlockIn, request: Request, response: Response) -> dict[str, Any]:
    if not demo_gate_required():
        raise NotFound("NOT_AVAILABLE", "Not available.")
    addr = _client_addr(request)
    if _unlock_blocked(addr):
        raise Throttled("TOO_MANY_ATTEMPTS", "Too many attempts. Wait a few minutes and try again.")
    if not access_code_matches(body.code):
        _remember_unlock_failure(addr)
        raise Forbidden("ACCESS_DENIED", "That access code was not accepted.")
    _unlock_failures.pop(addr, None)
    response.set_cookie(
        DEMO_COOKIE,
        sign_demo_gate(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "cloud",
        path="/",
    )
    return {"ok": True}


@app.get("/v1/dev/personas")
def personas(request: Request) -> dict[str, Any]:
    from ..seed import PUBLIC_PERSONAS

    if not dev_sign_in_allowed(request):
        raise NotFound("NOT_AVAILABLE", "Not available.")
    with global_session() as session:
        rows = session.execute(
            select(User, Membership, Organisation)
            .join(Membership, Membership.user_id == User.id)
            .join(Organisation, Organisation.id == Membership.org_id)
            .where(User.subject.in_(PUBLIC_PERSONAS))
            .order_by(Organisation.name, User.display_name)
        ).all()
    return {
        "personas": [
            {
                "subject": u.subject,
                "name": u.display_name,
                "title": u.title,
                "email": u.email,
                "organisation": o.name,
                "org_short": o.short_name,
                "roles": m.roles,
                "revoked": m.revoked_at is not None,
            }
            for u, m, o in rows
        ]
    }


class LoginIn(BaseModel):
    subject: str = Field(max_length=200)


@app.post("/v1/dev/login")
def dev_login(body: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    if not dev_sign_in_allowed(request):
        raise NotFound("NOT_AVAILABLE", "Not available.")
    if not body.subject.startswith("dev:"):
        raise Forbidden("NOT_A_DEV_IDENTITY", "Only seeded development identities can sign in here.")
    user, memberships = memberships_for(body.subject)
    if not memberships:
        raise Forbidden("NO_MEMBERSHIP", "This identity has no active membership.")
    org = memberships[0][1]
    data = new_session(body.subject, str(org.id))
    _set_session_cookie(response, data)
    return {"ok": True, "home": "/vendor" if body.subject == "dev:vendor" else "/queue"}


@app.post("/v1/session/logout")
def logout(response: Response) -> dict[str, Any]:
    secure = settings.environment == "cloud"
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax", httponly=True, secure=secure)
    response.delete_cookie(DEMO_COOKIE, path="/", samesite="lax", httponly=True, secure=secure)
    return {"ok": True}


class OrgIn(BaseModel):
    org_id: str


@app.post("/v1/session/organisation")
def switch_org(
    body: OrgIn, request: Request, response: Response, ctx: Ctx = Depends(current)
) -> dict[str, Any]:
    if ctx.session is None or request.headers.get("x-csrf-token") != csrf_token(ctx.session):
        raise Forbidden("CSRF", "The request is missing a valid anti-forgery token.")
    if not any(str(o.id) == body.org_id for _, o in ctx.memberships):
        raise Forbidden("NO_MEMBERSHIP", "You are not a member of that organisation.")
    data = SessionData(ctx.session.subject, ctx.session.sid, body.org_id)
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(data),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "cloud",
        path="/",
    )
    return {"ok": True}


@app.get("/v1/session")
def get_session(request: Request, response: Response, ctx: Ctx = Depends(current)) -> dict[str, Any]:
    session = ctx.session
    if session is None:  # hosted identity without a bound session yet: bind CSRF to a new session id
        session = new_session(ctx.user.subject, str(ctx.actor.org_id))
        response.set_cookie(
            SESSION_COOKIE,
            sign_session(session),
            max_age=SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
    org = next(o for _, o in ctx.memberships if o.id == ctx.actor.org_id)
    with org_session(ctx.actor.org_id) as s:
        tasks = s.execute(
            select(func.count()).select_from(HumanTask).where(HumanTask.state.in_(("pending", "claimed")))
        ).scalar_one()
        control = org_controls(s, ctx.actor.org_id)
        automation_enabled = control.automation_enabled
    return {
        "user": {
            "id": str(ctx.user.id),
            "name": ctx.user.display_name,
            "email": ctx.user.email,
            "title": ctx.user.title,
        },
        "organisation": {"id": str(org.id), "name": org.name, "short_name": org.short_name},
        "roles": sorted(ctx.actor.roles),
        "workspace": ctx.actor.workspace,
        "memberships": [{"org_id": str(o.id), "name": o.name, "roles": m.roles} for m, o in ctx.memberships],
        "csrf_token": csrf_token(session),
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "dev_identity": settings.dev_identity,
        "model": {
            "name": settings.model_name,
            "location": settings.model_location,
            "provider": settings.model_provider,
        },
        "counts": {"open_tasks": 0 if ctx.actor.workspace == "vendor" else int(tasks)},
        "automation_enabled": automation_enabled,
    }


# reference data


@app.get("/v1/catalog/scenarios")
def scenarios(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    parties = catalog.parties()
    return {
        "notice": catalog.catalog()["notice"],
        "scenarios": [
            {
                "key": s["key"],
                "title": s["title"],
                "family": s["family"],
                "description": s["description"],
                "walkthrough": s.get("walkthrough", []),
                "seller": parties[s["seller"]]["name"],
                "buyer": parties[s["buyer"]]["name"],
                "invoice_reference": s["invoice_reference"],
                "initial_documents": len(s["initial"]),
            }
            for s in catalog.scenarios()
        ],
    }


@app.get("/v1/policies")
def policies(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        rows = (
            session.execute(select(PolicyVersion).order_by(PolicyVersion.key, PolicyVersion.version.desc()))
            .scalars()
            .all()
        )
        return {
            "policies": [
                {
                    "id": str(p.id),
                    "key": p.key,
                    "version": p.version,
                    "name": p.name,
                    "status": p.status,
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "definition": definition_for(p),
                }
                for p in rows
            ],
            "can_publish": ctx.actor.has(ROLE_SUPERVISOR),
            "editor": editor_schema(),
            "limits": {
                "model_calls": settings.max_model_calls,
                "tool_calls": settings.max_tool_calls,
                "active_seconds": settings.max_active_seconds,
                "wakeups": settings.max_wakeups,
                "request_rounds": settings.max_request_rounds,
                "case_budget_usd": str(settings.case_budget_usd),
                "daily_budget_usd": str(settings.daily_budget_usd),
                "model": settings.model_name,
                "location": settings.model_location,
            },
        }


class PublishPolicyIn(BaseModel):
    base_policy_id: uuid.UUID
    definition: dict[str, Any]
    reason: str = Field(min_length=5, max_length=1200)


@app.post("/v1/policies/publish")
def publish_policy_version(body: PublishPolicyIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_SUPERVISOR)
    if len(body.reason.strip()) < 5:
        raise Unsupported("REASON_REQUIRED", "Explain the policy change using at least 5 characters.")

    def fn(session: Session) -> dict[str, Any]:
        policy = publish_policy(session, ctx.actor, body.base_policy_id, body.definition, body.reason.strip())
        return {"id": str(policy.id), "version": policy.version, "status": policy.status}

    return run_command(ctx, key, "POST /v1/policies/publish", body.model_dump(mode="json"), fn, status=201)


@app.get("/v1/members")
def members(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with global_session() as session:
        rows = session.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.org_id == ctx.actor.org_id, Membership.revoked_at.is_(None))
            .order_by(User.display_name)
        ).all()
    return {
        "members": [
            {"id": str(u.id), "name": u.display_name, "title": u.title, "roles": m.roles} for u, m in rows
        ]
    }


# cases


class ResearchRetryIn(BaseModel):
    expected_revision: int


@app.post("/v1/cases/{case_id}/credit-research/retry", status_code=202)
def retry_credit_research(
    case_id: str, body: ResearchRetryIn, cmd: tuple[Ctx, str] = Depends(command)
) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict:
        from ..casework import reopen_if_complete

        case = lock_case(session, load_case(session, case_id).id)
        if case.revision != body.expected_revision:
            raise StaleRevision(
                "STALE_REVISION", "Refresh the case before retrying research.", current_revision=case.revision
            )
        if case.lifecycle == "archived" or case.execution == "paused" or case.automation_mode != "autonomous":
            raise Conflict("RESEARCH_UNAVAILABLE", "Resume autonomous review before retrying research.")
        previous = case.credit_research or {}
        if previous.get("status") != "failed":
            raise Conflict(
                "RESEARCH_NOT_FAILED", "Only failed research can be retried; saved results are retained."
            )
        case.credit_research = {
            k: v for k, v in {**previous, "status": "pending"}.items() if k not in {"error", "completed_at"}
        }
        allocate_research_budget(case, ctx.actor, session)
        record(
            session,
            case,
            "CreditResearchRetryRequested",
            ctx.actor,
            "Retry public company research from saved progress",
            payload={"previous_error": previous.get("error")},
        )
        bump(case)
        reopen_if_complete(session, case, ctx.actor, "retrying public company research")
        enqueue_agent(session, case, "Continuation", "Retry public company research")
        settle_execution(session, case)
        return {"id": str(case.id), "revision": case.revision}

    return run_command(
        ctx, key, f"POST /v1/cases/{case_id}/credit-research/retry", body.model_dump(), fn, status=202
    )


@app.get("/v1/cases")
def get_cases(
    view: str = "all",
    assigned: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    ctx: Ctx = Depends(current),
) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        return list_cases(session, ctx.actor, view=view, assigned=assigned, query=q, cursor=cursor)


@app.get("/v1/research")
def get_research(
    status: Literal["all", "pending", "researching", "complete", "failed"] = "all",
    q: str | None = Query(default=None, max_length=200),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    ctx: Ctx = Depends(current),
) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        return list_research(session, ctx.actor, status=status, query=q, cursor=cursor, limit=limit)


class CreateCaseIn(BaseModel):
    scenario_key: str = Field(max_length=80)
    automation_mode: Literal["off", "shadow", "autonomous"] = "autonomous"
    assigned_to: str | None = None
    policy_id: str | None = None
    vendor_contact_id: str | None = Field(default=None, max_length=36)


@app.post("/v1/cases", status_code=202)
def post_case(body: CreateCaseIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict[str, Any]:
        if body.policy_id:
            policy = session.get(PolicyVersion, uuid.UUID(body.policy_id))
        else:
            policy = (
                session.execute(
                    select(PolicyVersion)
                    .where(PolicyVersion.status == "published")
                    .order_by(PolicyVersion.version.desc())
                )
                .scalars()
                .first()
            )
        if policy is None:
            raise NotFound("POLICY_NOT_FOUND", "No published policy is available.")
        assignee = uuid.UUID(body.assigned_to) if body.assigned_to else ctx.actor.user_id
        case = create_case(
            session,
            ctx.actor,
            policy=policy,
            scenario_key=body.scenario_key,
            assigned_to=assignee,
            automation_mode=body.automation_mode,
        )
        if body.vendor_contact_id:
            vendor.set_contact(session, case, ctx.actor, body.vendor_contact_id)
        enqueue_agent(
            session,
            case,
            "CaseCreated",
            f"{len(catalog.scenario(body.scenario_key)['initial'])} initial source(s)",
        )
        settle_execution(session, case)
        return {"id": str(case.id), "reference": case.reference, "revision": case.revision}

    return run_command(ctx, key, "POST /v1/cases", body.model_dump(), fn, status=202)


async def upload_form(
    request: Request, *, initial: bool, checks_only: bool = False
) -> tuple[list[Upload], dict[str, Any], list[Upload]]:
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise Unsupported("MULTIPART_REQUIRED", "Choose documents using the upload form.")
    async with request.form(max_files=MAX_FILES + 2, max_fields=12, max_part_size=8192) as form:
        uploads = []
        references = []
        fields: dict[str, Any] = {}
        for name, value in form.multi_items():
            if isinstance(value, UploadFile):
                is_reference = name in {"invoice_template", "receipt_template"}
                if is_reference and not (initial or checks_only):
                    raise Unsupported("CHECKS_FIXED", "Reference selections are fixed for this case.")
                if (not is_reference and name not in {"invoice", "receipts"}) or (
                    checks_only and not is_reference
                ):
                    raise Unsupported("INVALID_FILE_ROLE", "Choose an invoice or delivery receipt.")
                data = await value.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise Unsupported("FILE_TOO_LARGE", "Each document must be at most 10 MiB.")
                try:
                    mime = identify_format(data, value.filename or "")
                except (ValueError, OSError) as exc:
                    raise Unsupported("UNREADABLE_FORMAT", str(exc)) from exc
                if is_reference and mime != "application/pdf":
                    raise Unsupported(
                        "REFERENCE_PDF_REQUIRED",
                        "Appearance reference templates currently require PDF files.",
                    )
                filename = re.sub(
                    r"[\x00-\x1f\x7f]",
                    "",
                    (value.filename or "document.pdf").replace("\\", "/").split("/")[-1],
                )[:180]
                (references if is_reference else uploads).append(
                    Upload(
                        filename or "document.pdf",
                        "invoice" if name in {"invoice", "invoice_template"} else "delivery_receipt",
                        data,
                    )
                )
            elif (
                name
                in (
                    {"expected_revision", "tampering"}
                    if checks_only
                    else {"message", "sender", "expected_revision", "replaces"}
                    | (
                        {
                            "tampering",
                            "credit_research",
                            "research_target",
                            "company_country",
                            "registration_number",
                            "vendor_contact_id",
                        }
                        if initial
                        else set()
                    )
                )
                and name not in fields
            ):
                fields[name] = str(value).strip()
            else:
                raise Unsupported(
                    "INVALID_FIELD", "The upload form contains an unexpected or repeated field."
                )
    if (
        len(uploads) > MAX_FILES
        or len(references) > 2
        or sum(len(u.data) for u in uploads + references) > 20 * 1024 * 1024
    ):
        raise Unsupported("UPLOAD_LIMIT", "Choose at most 5 documents, totaling at most 20 MiB.")
    invoices = [u for u in uploads if u.role == "invoice"]
    if len(invoices) > 1 or (initial and len(invoices) != 1):
        raise Unsupported(
            "INVOICE_REQUIRED", "Start with one invoice document; supporting evidence is optional."
        )
    uploads.sort(key=lambda u: u.role != "invoice")  # baseline must be read before receipts
    if len(fields.get("message", "")) > 1200 or len(fields.get("sender", "")) > 200:
        raise Unsupported(
            "MESSAGE_LENGTH", "Replies allow up to 1,200 characters and sender names up to 200."
        )
    if not checks_only and not uploads and not fields.get("message"):
        raise Unsupported("INPUT_REQUIRED", "Add a document or write a reply.")
    if fields.get("replaces"):
        if initial or len(uploads) != 1:
            raise Unsupported(
                "ONE_CORRECTION", "Upload one correction at a time when replacing an earlier document."
            )
        try:
            uuid.UUID(fields["replaces"])
        except ValueError as exc:
            raise Unsupported("INVALID_REPLACEMENT", "Choose an existing document to replace.") from exc
        uploads[0].replaces = fields["replaces"]
    if not initial:
        try:
            fields["expected_revision"] = int(fields["expected_revision"])
        except (ValueError, KeyError) as exc:
            raise Unsupported("REVISION_REQUIRED", "Refresh the case before adding documents.") from exc
    if fields.get("tampering", "false") not in {"true", "false"}:
        raise Unsupported("INVALID_CHECK_OPTION", "Choose whether to check for possible tampering.")
    fields["tampering"] = fields.get("tampering") == "true"
    if initial:
        if len(fields.get("vendor_contact_id", "")) > 36:
            raise Unsupported("INVALID_VENDOR_CONTACT", "Choose an active vendor contact.")
        if fields.get("credit_research", "false") not in {"true", "false"}:
            raise Unsupported("INVALID_RESEARCH_OPTION", "Choose whether to research the company.")
        if fields.get("research_target", "buyer") not in {"buyer", "seller"}:
            raise Unsupported("INVALID_RESEARCH_TARGET", "Choose the buyer or seller named on the invoice.")
        if any(len(fields.get(name, "")) > 80 for name in ("company_country", "registration_number")):
            raise Unsupported("COMPANY_ID_LENGTH", "Company identifiers allow up to 80 characters.")
    return uploads, fields, references


@app.post("/v1/cases/upload", status_code=202)
@app.post("/v1/vendor/cases", status_code=202)
async def post_uploaded_case(request: Request, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_VENDOR)
    uploads, fields, references = await upload_form(request, initial=True)
    if ctx.actor.workspace == "vendor":
        if references or fields["tampering"] or fields.get("sender") or "vendor_contact_id" in fields:
            raise Forbidden(
                "BANK_REVIEW_OPTIONS", "The bank sets review checks. Replies use your signed-in name."
            )
        fields["sender"] = ctx.actor.name

    def fn(session: Session) -> dict[str, Any]:
        assignee = (
            vendor.reviewer_for(session, ctx.actor) if ctx.actor.workspace == "vendor" else ctx.actor.user_id
        )
        case = create_uploaded_case(
            session,
            ctx.actor,
            uploads,
            fields.get("message", ""),
            fields.get("sender", ""),
            tampering=fields["tampering"],
            references=references,
            research=ResearchOptions(
                enabled=fields.get("credit_research") == "true",
                target=fields.get("research_target", "buyer"),
                country=fields.get("company_country", ""),
                registration_number=fields.get("registration_number", ""),
            ),
        )
        case.assigned_to = assignee
        if fields.get("vendor_contact_id"):
            vendor.set_contact(session, case, ctx.actor, fields["vendor_contact_id"])
        enqueue_agent(session, case, "CaseCreated", "Read uploaded invoice and receipts")
        settle_execution(session, case)
        return {"id": str(case.id), "reference": case.reference, "revision": case.revision}

    return await run_in_threadpool(
        run_command,
        ctx,
        key,
        f"POST {request.url.path}",
        {
            "files": [u.fingerprint() for u in uploads],
            "references": [u.fingerprint() for u in references],
            **fields,
        },
        fn,
        202,
    )


@app.post("/v1/cases/{case_id}/inputs", status_code=202)
@app.post("/v1/vendor/cases/{case_id}/inputs", status_code=202)
async def post_case_input(
    case_id: str, request: Request, cmd: tuple[Ctx, str] = Depends(command)
) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR, ROLE_SIMULATION, ROLE_VENDOR)
    uploads, fields, _ = await upload_form(request, initial=False)
    if ctx.actor.workspace == "vendor":
        if fields.get("sender"):
            raise Forbidden("SENDER_FIXED", "Replies use your signed-in name.")
        fields["sender"] = ctx.actor.name

    def fn(session: Session) -> dict[str, Any]:
        case = load_case(session, case_id)
        if ctx.actor.workspace == "vendor":
            vendor.require_access(case, ctx.actor)
        case = lock_case(session, case.id)
        if case.revision != fields["expected_revision"]:
            raise StaleRevision(
                "STALE_REVISION",
                "The case changed. Review the latest state and submit again.",
                current_revision=case.revision,
            )
        reply, created = add_input(
            session, case, ctx.actor, uploads, fields.get("message", ""), fields.get("sender", "")
        )
        if created:
            enqueue_agent(session, case, "ReplyReceived", reply.summary)
            settle_execution(session, case)
        return {"id": str(reply.id), "revision": case.revision}

    return await run_in_threadpool(
        run_command,
        ctx,
        key,
        f"POST {request.url.path}",
        {"files": [u.fingerprint() for u in uploads], **fields},
        fn,
        202,
    )


@app.post("/v1/cases/{case_id}/document-checks", status_code=202)
async def enable_document_checks(
    case_id: str, request: Request, cmd: tuple[Ctx, str] = Depends(command)
) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)
    _, fields, references = await upload_form(request, initial=False, checks_only=True)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id)
        if case.revision != fields["expected_revision"]:
            raise StaleRevision(
                "STALE_REVISION",
                "Refresh the case before enabling document checks.",
                current_revision=case.revision,
            )
        configure_checks(session, case, ctx.actor, fields["tampering"], references)
        enqueue_agent(session, case, "DocumentChecksEnabled", "Run optional document appearance checks")
        settle_execution(session, case)
        return {"id": str(case.id), "revision": case.revision}

    return await run_in_threadpool(
        run_command,
        ctx,
        key,
        f"POST /v1/cases/{case_id}/document-checks",
        {"references": [u.fingerprint() for u in references], **fields},
        fn,
        202,
    )


@app.get("/v1/cases/{case_id}/document-checks/templates/{role}/{format}")
def document_reference(
    case_id: str,
    role: Literal["invoice", "delivery_receipt"],
    format: Literal["preview", "original"],
    page: int = 1,
    ctx: Ctx = Depends(current),
) -> Response:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        reference = (case.document_checks or {}).get("references", {}).get(role)
        if not reference or not 1 <= page <= reference["page_count"]:
            raise NotFound("REFERENCE_NOT_FOUND", "Reference document or page not found.")
        data = object_store().get(reference["object_key"], reference["object_generation"])
        if hashlib.sha256(data).hexdigest() != reference["sha256"]:
            raise Conflict("REFERENCE_ALTERED", "The reference does not match its saved hash.")
        record(
            session,
            case,
            "ReferenceViewed",
            ctx.actor,
            f"Viewed {role} reference",
            payload={"sha256": reference["sha256"]},
        )
    if format == "preview":
        return Response(
            render_preview(data, page - 1, scale=1.2),
            media_type="image/png",
            headers={"Cache-Control": "private, no-store"},
        )
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{role}-reference.pdf"'},
    )


@app.get("/v1/cases/{case_id}")
def get_case(case_id: str, request: Request, ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        etag = f'W/"{etag_for(case)}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        body = case_detail(session, ctx.actor, case)
    return JSONResponse(
        content=json.loads(json.dumps(body, default=str)), headers={"ETag": etag, "Cache-Control": "no-cache"}
    )


class ApplyPolicyIn(BaseModel):
    policy_id: uuid.UUID
    expected_revision: int
    reason: str = Field(min_length=5, max_length=1000)


@app.post("/v1/cases/{case_id}/policy", status_code=202)
def apply_case_policy(
    case_id: str, body: ApplyPolicyIn, cmd: tuple[Ctx, str] = Depends(command)
) -> JSONResponse:
    from ..policies import apply_version

    ctx, key = cmd
    require(ctx.actor, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict:
        case = lock_case(session, load_case(session, case_id).id)
        if case.revision != body.expected_revision:
            raise StaleRevision(
                "STALE_REVISION",
                "Refresh the case before applying a policy version.",
                current_revision=case.revision,
            )
        if len(body.reason.strip()) < 5:
            raise Unsupported("REASON_REQUIRED", "Explain why the updated policy applies to this case.")
        apply_version(session, case, ctx.actor, body.policy_id, body.reason.strip())
        enqueue_agent(session, case, "PolicyUpdated", "Re-evaluate documents under the selected policy")
        settle_execution(session, case)
        return {"id": str(case.id), "revision": case.revision}

    return run_command(
        ctx, key, f"POST /v1/cases/{case_id}/policy", body.model_dump(mode="json"), fn, status=202
    )


@app.get("/v1/cases/{case_id}/status")
def get_case_status(case_id: str, request: Request, ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        etag = f'W/"{etag_for(case)}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        body = {
            "revision": case.revision,
            "execution": case.execution,
            "lifecycle": case.lifecycle,
            "etag": etag_for(case),
        }
    return JSONResponse(content=body, headers={"ETag": etag, "Cache-Control": "no-cache"})


@app.get("/v1/cases/{case_id}/history")
def history(case_id: str, before: int | None = None, ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        stmt = select(AuditEvent).where(AuditEvent.case_id == case.id)
        if before:
            stmt = stmt.where(AuditEvent.id < before)
        rows = session.execute(stmt.order_by(AuditEvent.id.desc()).limit(200)).scalars().all()
        return {
            "events": [audit_json(e) for e in rows],
            "next_cursor": rows[-1].id if len(rows) == 200 else None,
        }


def _version(session: Session, case: Case, version_id: str) -> DocumentVersion:
    try:
        vid = uuid.UUID(version_id)
    except ValueError as exc:
        raise NotFound("SOURCE_NOT_FOUND", "Source not found.") from exc
    version = session.get(DocumentVersion, vid)
    if version is None or version.case_id != case.id:
        raise NotFound("SOURCE_NOT_FOUND", "Source not found.")
    return version


@app.get("/v1/cases/{case_id}/sources/{version_id}/preview")
def preview(case_id: str, version_id: str, page: int = 1, ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        version = _version(session, case, version_id)
        rendered = (version.structured or {}).get("rendered_document")
        if not version.object_key or not (
            version.mime == "application/pdf" or (version.mime or "").startswith("image/") or rendered
        ):
            raise Unsupported("NO_PREVIEW", "This source has no document preview.")
        if not 1 <= page <= (version.page_count or 1):
            raise NotFound("PAGE_NOT_FOUND", "Page not found.")
        key, sha, mime = version.object_key, version.sha256, version.mime
        if rendered:
            key, sha, mime = rendered["object_key"], rendered["sha256"], rendered["mime"]
    store = object_store()
    derived = f"orgs/{ctx.actor.org_id}/cases/{case_id}/previews/{sha}-p{page}.png"
    if store.exists(derived):
        png = store.get(derived)
    else:
        original = store.get(key)
        if hashlib.sha256(original).hexdigest() != sha:
            raise Conflict("ORIGINAL_ALTERED", "The stored original does not match its registered hash.")
        png = (
            render_preview(original, page - 1)
            if mime == "application/pdf"
            else image_preview(original, page - 1)
        )
        store.put_immutable(derived, png)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@app.get("/v1/cases/{case_id}/sources/{version_id}/original")
def original(case_id: str, version_id: str, ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        version = _version(session, case, version_id)
        if not version.object_key:
            raise Unsupported("NO_ORIGINAL", "This source has no stored file.")
        key, sha, label, mime = version.object_key, version.sha256, version.label, version.mime
        record(session, case, "OriginalDownloaded", ctx.actor, f"{ctx.actor.name} downloaded {label}")
    data = object_store().get(key)
    if hashlib.sha256(data).hexdigest() != sha:
        raise Conflict("ORIGINAL_ALTERED", "The stored original does not match its registered hash.")
    return Response(
        content=data,
        media_type=mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{case_id[:8]}-{label}.{EXTENSIONS.get(mime, "bin")}"'
        },
    )


@app.get("/v1/vendor/cases")
def vendor_cases(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        cases = session.execute(
            select(Case)
            .where(Case.vendor_contact_id == ctx.actor.user_id)
            .order_by(Case.updated_at.desc(), Case.id)
        ).scalars()
        return {"items": [vendor.summary(case) for case in cases]}


@app.get("/v1/vendor/cases/{case_id}")
def vendor_case(case_id: str, ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        return vendor.detail(session, ctx.actor, load_case(session, case_id))


@app.get("/v1/vendor/cases/{case_id}/sources/{version_id}/original")
def vendor_original(case_id: str, version_id: str, ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        vendor.require_access(load_case(session, case_id), ctx.actor)
    return original(case_id, version_id, ctx)


class AutomationIn(BaseModel):
    action: Literal["pause", "resume", "set_mode"]
    mode: Literal["off", "shadow", "autonomous"] | None = None
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int


@app.post("/v1/cases/{case_id}/automation", status_code=202)
def automation(case_id: str, body: AutomationIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id, body.expected_revision)
        if body.action == "pause":
            if case.execution == "paused":
                raise Conflict("ALREADY_PAUSED", "Automation is already paused for this case.")
            bump(case)
            record_pause(
                session, case, ctx.actor, "SUPERVISOR_PAUSE", f"Paused by {ctx.actor.name}: {body.reason}"
            )
        elif body.action == "resume":
            if case.execution != "paused":
                raise Conflict("NOT_PAUSED", "Automation is not paused for this case.")
            bump(case)
            case.execution = "idle"
            case.paused_reason = None
            record(
                session,
                case,
                "AutomationResumed",
                ctx.actor,
                f"Automation resumed by {ctx.actor.name}",
                reason=body.reason,
            )
            enqueue_agent(session, case, "RecoveryRequested", body.reason)
            settle_execution(session, case)
        else:
            if body.mode is None or body.mode == case.automation_mode:
                raise Conflict("MODE_UNCHANGED", "Choose a different automation mode.")
            bump(case)
            previous = case.automation_mode
            case.automation_mode = body.mode
            record(
                session,
                case,
                "AutomationModeChanged",
                ctx.actor,
                f"Automation mode {previous} → {body.mode}",
                reason=body.reason,
                payload={"from": previous, "to": body.mode},
            )
            if body.mode != "off":
                enqueue_agent(session, case, "ModeChanged", f"{previous} → {body.mode}")
            settle_execution(session, case)
        return {"revision": case.revision, "execution": case.execution, "mode": case.automation_mode}

    return run_command(ctx, key, f"POST /v1/cases/{case_id}/automation", body.model_dump(), fn, status=202)


class ManualIn(BaseModel):
    action: Literal["run_checks", "request_open_items", "complete"]
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int


@app.post("/v1/cases/{case_id}/manual")
def manual(case_id: str, body: ManualIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    """Manual fallback with the same identity, source, revision and audit controls. It cannot waive failed checks."""
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id, body.expected_revision)
        if case.automation_mode == "autonomous" and case.execution != "paused":
            raise Conflict(
                "AUTOMATION_ACTIVE",
                "Manual actions are available when automation is off, in shadow or paused.",
            )
        bump(case)
        record(
            session,
            case,
            "ManualAction",
            ctx.actor,
            f"{ctx.actor.name}: manual {body.action.replace('_', ' ')}",
            reason=body.reason,
        )
        if body.action == "run_checks":
            results = apply_checks(session, case, ctx.actor, resolve=True)
            out = {k: r.as_dict() for k, r in results.items()}
        elif body.action == "request_open_items":
            from ..casework import outstanding_question_ids, policy_of, questions_of
            from ..requests import allowed_templates

            outstanding = outstanding_question_ids(session, case.id)
            active_keys = {rule["key"] for rule in policy_of(session, case).definition["requirements"]}
            items = [
                {"question_id": str(q.id), "template_id": None}
                for q in questions_of(session, case.id).values()
                if q.requirement_key in active_keys
                and q.state != "resolved"
                and q.id not in outstanding
                and allowed_templates(q, False)
            ]
            if not items:
                raise Conflict(
                    "NOTHING_TO_REQUEST", "No open question can be requested with an approved template."
                )
            request = prepare_request(session, case, ctx.actor, items=items, created_by="person")
            _, code = issue_request(session, case, ctx.actor, request.id)
            out = {"request_id": str(request.id), "result": code}
        else:
            ok, blockers, export = try_complete(session, case, ctx.actor)
            if not ok:
                raise Conflict("NOT_COMPLETE", "Completion prerequisites are not met.", blockers=blockers)
            out = {"export_ref": export.export_ref if export else None}
        settle_execution(session, case)
        return {"revision": case.revision, "result": out}

    return run_command(ctx, key, f"POST /v1/cases/{case_id}/manual", body.model_dump(), fn)


class AssignIn(BaseModel):
    user_id: str
    expected_revision: int


class VendorContactIn(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)
    expected_revision: int


@app.post("/v1/cases/{case_id}/vendor-contact")
def vendor_contact(
    case_id: str, body: VendorContactIn, cmd: tuple[Ctx, str] = Depends(command)
) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict:
        case = lock_case(session, load_case(session, case_id).id, body.expected_revision)
        vendor.set_contact(session, case, ctx.actor, body.user_id)
        return {"revision": case.revision}

    return run_command(ctx, key, f"POST /v1/cases/{case_id}/vendor-contact", body.model_dump(), fn)


@app.post("/v1/cases/{case_id}/assignment")
def assign(case_id: str, body: AssignIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id, body.expected_revision)
        member = session.execute(
            select(Membership).where(
                Membership.org_id == case.org_id,
                Membership.user_id == uuid.UUID(body.user_id),
                Membership.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if member is None or not ({"reviewer", "supervisor"} & set(member.roles)):
            raise Unsupported("NOT_A_REVIEWER", "Cases can be assigned to active reviewers only.")
        bump(case)
        case.assigned_to = member.user_id
        record(
            session,
            case,
            "CaseAssigned",
            ctx.actor,
            "Case assignment changed",
            payload={"user_id": body.user_id},
        )
        return {"revision": case.revision}

    return run_command(ctx, key, f"POST /v1/cases/{case_id}/assignment", body.model_dump(), fn)


# exports


@app.get("/v1/exports/{export_id}/{fmt}")
def download_export(export_id: str, fmt: Literal["pdf", "json"], ctx: Ctx = Depends(current)) -> Response:
    with org_session(ctx.actor.org_id) as session:
        try:
            export = session.get(Export, uuid.UUID(export_id))
        except ValueError:
            export = None
        if export is None:
            raise NotFound("EXPORT_NOT_FOUND", "Export not found.")
        if export.state not in ("ready", "superseded") or not export.pdf_key:
            raise Conflict("EXPORT_NOT_READY", f"The summary is {export.state}.")
        key = export.pdf_key if fmt == "pdf" else export.json_key
        case = session.get(Case, export.case_id)
        current_flag = (
            "current" if case.current_export_id == export.id and export.state == "ready" else "superseded"
        )
        ref = export.export_ref
        record(
            session,
            case,
            "ExportDownloaded",
            ctx.actor,
            f"{ctx.actor.name} downloaded {ref} ({fmt}, {current_flag})",
        )
    data = object_store().get(key)
    return Response(
        content=data,
        media_type="application/pdf" if fmt == "pdf" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{ref}.{fmt}"',
            "X-Export-Status": current_flag,
        },
    )


@app.post("/v1/cases/{case_id}/exports/retry", status_code=202)
def retry_export(case_id: str, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    require(ctx.actor, ROLE_REVIEWER, ROLE_SUPERVISOR)

    def fn(session: Session) -> dict[str, Any]:
        case = load_case(session, case_id)
        export = session.get(Export, case.current_export_id) if case.current_export_id else None
        if export is None or export.state not in ("failed", "preparing"):
            raise Conflict("NOTHING_TO_RETRY", "The current summary does not need a retry.")
        export.state = "preparing"
        job = Job(
            org_id=case.org_id,
            case_id=case.id,
            kind="export",
            trigger="ExportRequested",
            input_revision=case.revision,
            export_id=export.id,
        )
        session.add(job)
        session.flush()
        from ..history import emit

        emit(session, case.org_id, "JobQueued", case_id=case.id, job_id=job.id, payload={"kind": "export"})
        return {"export_ref": export.export_ref}

    return run_command(ctx, key, f"POST /v1/cases/{case_id}/exports/retry", {}, fn, status=202)


# tasks


@app.get("/v1/tasks")
def tasks(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    with org_session(ctx.actor.org_id) as session:
        return {"tasks": task_inbox(session, ctx.actor)}


@app.post("/v1/tasks/{task_id}/claim")
def claim_task(task_id: str, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd

    def fn(session: Session) -> dict[str, Any]:
        task = claim(session, uuid.UUID(task_id), ctx.actor)
        return {"state": task.state, "claim_expires_at": task.claim_expires_at.isoformat()}

    return run_command(ctx, key, f"POST /v1/tasks/{task_id}/claim", {}, fn)


@app.post("/v1/tasks/{task_id}/release")
def release_task(task_id: str, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd

    def fn(session: Session) -> dict[str, Any]:
        task = release(session, uuid.UUID(task_id), ctx.actor)
        return {"state": task.state}

    return run_command(ctx, key, f"POST /v1/tasks/{task_id}/release", {}, fn)


class DecisionIn(BaseModel):
    decision_type: str = Field(max_length=60)
    reason: str = Field(max_length=2000)
    expected_revision: int
    covered_version_ids: list[str] = Field(default_factory=list, max_length=20)
    params: dict[str, Any] = Field(default_factory=dict)


@app.post("/v1/tasks/{task_id}/decisions", status_code=202)
def post_decision(task_id: str, body: DecisionIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd

    def fn(session: Session) -> dict[str, Any]:
        decision = decide(
            session,
            uuid.UUID(task_id),
            ctx.actor,
            decision_type=body.decision_type,
            reason=body.reason,
            expected_revision=body.expected_revision,
            covered_version_ids=body.covered_version_ids,
            params=body.params,
        )
        case = session.get(Case, decision.case_id)
        return {"decision_id": str(decision.id), "revision": case.revision, "execution": case.execution}

    return run_command(ctx, key, f"POST /v1/tasks/{task_id}/decisions", body.model_dump(), fn, status=202)


# simulation


def _demo_only(ctx: Ctx) -> None:
    if not settings.demo_mode:
        raise NotFound("NOT_AVAILABLE", "The customer simulator is not available in this environment.")
    require(ctx.actor, ROLE_SIMULATION)


@app.get("/v1/demo/cases/{case_id}/responses")
def staged_options(case_id: str, ctx: Ctx = Depends(current)) -> dict[str, Any]:
    _demo_only(ctx)
    from ..models import Reply

    with org_session(ctx.actor.org_id) as session:
        case = load_case(session, case_id)
        sent = {
            r.staged_key for r in session.execute(select(Reply).where(Reply.case_id == case.id)).scalars()
        }
        sc = catalog.scenario(case.scenario_key)
        parties = catalog.parties()
        return {
            "responses": [
                {
                    "key": s["key"],
                    "label": s["label"],
                    "kind": s["kind"],
                    "sender": parties[s["sender"]]["name"],
                    "already_sent": s["key"] in sent,
                }
                for s in sc["staged"]
            ],
            "compose_enabled": settings.allow_composed_messages,
            "walkthrough": sc.get("walkthrough", []),
            "seller": case.seller["name"],
        }


class StagedIn(BaseModel):
    staged_key: str | None = Field(default=None, max_length=80)
    composed_text: str | None = Field(default=None, max_length=1200)


@app.post("/v1/demo/cases/{case_id}/responses", status_code=202)
def post_staged(case_id: str, body: StagedIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    _demo_only(ctx)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id)
        reply, created = receive_staged_response(
            session, case, ctx.actor, staged_key=body.staged_key, composed_text=body.composed_text
        )
        if created:
            enqueue_agent(session, case, "ReplyReceived", reply.summary)
            settle_execution(session, case)
        return {"reply_id": str(reply.id), "created": created, "revision": case.revision}

    return run_command(
        ctx, key, f"POST /v1/demo/cases/{case_id}/responses", body.model_dump(), fn, status=202
    )


class ClockIn(BaseModel):
    hours: int = Field(ge=1, le=336)


@app.post("/v1/demo/cases/{case_id}/clock")
def post_clock(case_id: str, body: ClockIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    _demo_only(ctx)

    def fn(session: Session) -> dict[str, Any]:
        case = lock_case(session, load_case(session, case_id).id)
        moved = advance_demo_clock(session, case, ctx.actor, body.hours)
        from ..requests import due_timer_effects

        effects = due_timer_effects(session, case)
        settle_execution(session, case)
        return {"timers_moved": moved, "effects": effects, "revision": case.revision}

    return run_command(ctx, key, f"POST /v1/demo/cases/{case_id}/clock", body.model_dump(), fn)


# operations


@app.get("/v1/operations")
def operations(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    require(ctx.actor, ROLE_SUPERVISOR, ROLE_ADMIN, ROLE_AUDITOR, ROLE_REVIEWER)
    now = utcnow()
    day = now.strftime("%Y-%m-%d")
    with org_session(ctx.actor.org_id) as session:
        control = org_controls(session, ctx.actor.org_id)
        cases = session.execute(select(Case)).scalars().all()
        policy_limits = {
            p.id: definition_for(p)["limits"] for p in session.execute(select(PolicyVersion)).scalars()
        }
        case_limits = {c.id: policy_limits[c.policy_id] for c in cases}
        by_exec: dict[str, int] = {}
        for c in cases:
            key = "complete" if c.lifecycle == "complete" else c.execution
            by_exec[key] = by_exec.get(key, 0) + 1
        queued = session.execute(select(Job).where(Job.state.in_(("queued", "leased")))).scalars().all()
        oldest = min((j.created_at for j in queued if j.state == "queued"), default=None)
        calls = session.execute(select(ProviderCall).where(ProviderCall.usage_day == day)).scalars().all()
        runs = (
            session.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(25)).scalars().all()
        )
        refs = {c.id: c.reference for c in cases}
        paused = [
            {
                "id": str(c.id),
                "reference": c.reference,
                "title": c.title,
                "reason": c.paused_reason,
                "next_action": c.next_action,
            }
            for c in cases
            if c.execution == "paused"
        ]
        tasks_open = session.execute(
            select(func.count()).select_from(HumanTask).where(HumanTask.state.in_(("pending", "claimed")))
        ).scalar_one()
        errors = [c for c in calls if c.status == "error"]
        latencies = sorted(c.latency_ms for c in calls if c.status == "ok" and c.latency_ms)
        p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else None
        stale_runs = session.execute(
            select(func.count()).select_from(AgentRun).where(AgentRun.outcome == "stale")
        ).scalar_one()
        return {
            "controls": {
                "automation_enabled": control.automation_enabled,
                "revision": control.revision,
                "model_fault": control.model_fault,
                "model_fault_remaining": control.model_fault_remaining,
                "reason": control.reason,
                "updated_at": control.updated_at.isoformat(),
            },
            "cases": by_exec,
            "case_total": len(cases),
            "open_tasks": int(tasks_open),
            "paused": paused,
            "queue": {
                "queued": sum(1 for j in queued if j.state == "queued"),
                "running": sum(1 for j in queued if j.state == "leased"),
                "oldest_queued_seconds": int((now - oldest).total_seconds()) if oldest else 0,
            },
            "model": {
                "name": settings.model_name,
                "location": settings.model_location,
                "calls_today": len(calls),
                "errors_today": len(errors),
                "error_codes": sorted({c.error_code for c in errors if c.error_code}),
                "cost_today_usd": str(
                    sum(
                        (Decimal(c.cost_usd if c.cost_usd is not None else c.reserved_usd) for c in calls),
                        Decimal(0),
                    )
                ),
                "daily_budget_usd": str(settings.daily_budget_usd),
                "p95_latency_ms": p95,
                "input_tokens_today": sum(c.input_tokens or 0 for c in calls),
                "output_tokens_today": sum((c.output_tokens or 0) + (c.thinking_tokens or 0) for c in calls),
            },
            "stale_rejections": int(stale_runs),
            "recent_runs": [
                {
                    "id": str(r.id),
                    "case_id": str(r.case_id),
                    "case_reference": refs.get(r.case_id),
                    "trigger": r.trigger,
                    "controller": r.controller,
                    "outcome": r.outcome,
                    "stop_reason": r.stop_reason,
                    "model_calls": r.model_calls,
                    "tool_calls": r.tool_calls,
                    "model_calls_limit": case_limits[r.case_id]["model_calls_per_invocation"],
                    "tool_calls_limit": case_limits[r.case_id]["tool_calls_per_invocation"],
                    "cost_usd": str(r.cost_usd),
                    "started_at": r.started_at.isoformat(),
                    "duration_s": round((r.ended_at - r.started_at).total_seconds(), 1)
                    if r.ended_at
                    else None,
                }
                for r in runs
            ],
            "limits": {
                "model_calls": settings.max_model_calls,
                "tool_calls": settings.max_tool_calls,
                "active_seconds": settings.max_active_seconds,
                "wakeups": settings.max_wakeups,
                "case_budget_usd": str(settings.case_budget_usd),
                "global_concurrency": settings.global_concurrency,
                "org_concurrency": settings.org_concurrency,
            },
        }


class ControlsIn(BaseModel):
    automation_enabled: bool | None = None
    model_fault: Literal["timeout", "quota", "none"] | None = None
    fault_count: int = Field(default=3, ge=1, le=10)
    reason: str = Field(min_length=5, max_length=500)
    expected_control_revision: int


@app.post("/v1/operations/controls")
def controls(body: ControlsIn, cmd: tuple[Ctx, str] = Depends(command)) -> JSONResponse:
    ctx, key = cmd
    if body.automation_enabled is not None:
        require(ctx.actor, ROLE_SUPERVISOR)
    if body.model_fault is not None:
        require(ctx.actor, ROLE_ADMIN)
        if not settings.demo_mode:
            raise Forbidden(
                "NOT_AVAILABLE", "Fault injection is available only in the demonstration environment."
            )

    def fn(session: Session) -> dict[str, Any]:
        control = org_controls(session, ctx.actor.org_id)
        session.refresh(control, with_for_update=True)
        if control.revision != body.expected_control_revision:
            raise StaleRevision("STALE_CONTROLS", "Controls changed since you loaded them.")
        control.revision += 1
        control.updated_at = utcnow()
        control.updated_by = ctx.actor.user_id
        control.reason = body.reason
        summary = []
        if body.automation_enabled is not None and body.automation_enabled != control.automation_enabled:
            control.automation_enabled = body.automation_enabled
            summary.append(
                "Automation " + ("resumed" if body.automation_enabled else "stopped (emergency stop)")
            )
        if body.model_fault is not None:
            control.model_fault = None if body.model_fault == "none" else body.model_fault
            control.model_fault_remaining = 0 if body.model_fault == "none" else body.fault_count
            summary.append(
                "Fault injection: "
                + (
                    f"next {body.fault_count} model call(s) fail with {body.model_fault}"
                    if body.model_fault != "none"
                    else "cleared"
                )
            )
        record(
            session,
            None,
            "ControlsChanged",
            ctx.actor,
            "; ".join(summary) or "Controls unchanged",
            reason=body.reason,
            org_id=ctx.actor.org_id,
            payload={"revision": control.revision},
        )
        return {
            "revision": control.revision,
            "automation_enabled": control.automation_enabled,
            "model_fault": control.model_fault,
        }

    return run_command(ctx, key, "POST /v1/operations/controls", body.model_dump(), fn)


@app.get("/v1/evaluation")
def evaluation(ctx: Ctx = Depends(current)) -> dict[str, Any]:
    from ..config import APP_ROOT

    path = APP_ROOT / "evaluation" / "results" / "latest.json"
    if not path.exists():
        return {"available": False}
    return {"available": True, "report": json.loads(path.read_text())}
