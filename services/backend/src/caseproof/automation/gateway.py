"""Vertex AI model gateway: the only path to Gemini.

Every provider call — the ADK agent's steps and nested comparison calls — reserves worst-case spend against
the case and daily allowances before it is made, counts toward the invocation's model-call and time limits,
and is reconciled with reported usage afterwards. Unknown usage keeps its reservation. SDK retries are
disabled; transient retries are explicit and counted.
"""

from __future__ import annotations

import asyncio
import contextvars
import time
import uuid
import weakref
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy import func, select

from ..config import get_settings
from ..db import org_session
from ..models import Case, OrgControl, ProviderCall


class BudgetExceeded(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ModelUnavailable(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class TransientModelError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class RunContext:
    org_id: uuid.UUID
    case_id: uuid.UUID
    job_id: uuid.UUID
    lease_token: uuid.UUID
    run_id: uuid.UUID
    mode: str
    controller: str
    expected_revision: int
    trigger: str
    started: float = field(default_factory=time.monotonic)
    model_calls: int = 0
    tool_calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    seq: int = 0
    terminal: str | None = None  # waiting | human_task | completed | stale | paused | shadow
    stop_reason: str = ""
    summary_parts: list[str] = field(default_factory=list)
    policy_settings: dict[str, Any] = field(default_factory=dict)

    def limit(self, key: str, fallback: int | float) -> int:
        return int(self.policy_settings.get(key, fallback))

    def time_left(self) -> float:
        return self.limit("active_seconds_per_invocation", get_settings().max_active_seconds) - (
            time.monotonic() - self.started
        )


current_run: contextvars.ContextVar[RunContext | None] = contextvars.ContextVar("current_run", default=None)

_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, genai.Client]" = weakref.WeakKeyDictionary()


def vertex_client() -> genai.Client:
    """One client per event loop: async HTTP connections cannot be shared across loops."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        s = get_settings()
        client = genai.Client(
            vertexai=True,
            project=s.gcp_project,
            location=s.model_location,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1), timeout=int(s.model_timeout_s * 1000)
            ),
        )
        _clients[loop] = client
    return client


def worst_case_cost(input_tokens: int, output_tokens: int | None = None) -> Decimal:
    s = get_settings()
    return (
        Decimal(input_tokens) * s.price_input_per_mtok
        + Decimal(output_tokens or s.max_output_tokens) * s.price_output_per_mtok
    ) / Decimal(1_000_000)


def actual_cost(input_tokens: int, output_tokens: int) -> Decimal:
    s = get_settings()
    return (
        Decimal(input_tokens) * s.price_input_per_mtok + Decimal(output_tokens) * s.price_output_per_mtok
    ) / Decimal(1_000_000)


def estimate_tokens(text_length: int) -> int:
    return max(200, text_length // 3)  # conservative: ~3 characters per token


def reserve(
    ctx: RunContext,
    purpose: str,
    est_input_tokens: int,
    *,
    search: bool = False,
    output_tokens: int | None = None,
) -> uuid.UUID:
    s = get_settings()
    max_calls = ctx.limit("model_calls_per_invocation", s.max_model_calls)
    if ctx.model_calls >= max_calls:
        raise BudgetExceeded(
            "MODEL_CALL_LIMIT", f"The invocation reached its limit of {max_calls} model calls."
        )
    if ctx.time_left() <= 2:
        raise BudgetExceeded(
            "TIME_LIMIT",
            f"The invocation reached its {ctx.limit('active_seconds_per_invocation', s.max_active_seconds)}-second limit.",
        )
    if est_input_tokens > s.max_input_tokens:
        raise BudgetExceeded("PAYLOAD_LIMIT", "The model input exceeds the 20,000-token payload limit.")
    if s.price_input_per_mtok <= 0 or s.price_output_per_mtok <= 0:
        raise BudgetExceeded("PRICING_MISSING", "Model pricing is not configured; calls are disabled.")
    amount = worst_case_cost(est_input_tokens, output_tokens)
    if search:
        if s.search_price_per_query <= 0 or s.search_reserve_queries < 1:
            raise BudgetExceeded("PRICING_MISSING", "Search pricing is not configured.")
        amount += s.search_price_per_query * s.search_reserve_queries
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    with org_session(ctx.org_id) as session:
        case = session.execute(select(Case).where(Case.id == ctx.case_id).with_for_update()).scalar_one()
        if Decimal(case.cost_reserved_usd) + amount > Decimal(case.budget_usd):
            raise BudgetExceeded(
                "CASE_BUDGET", f"The case model budget (USD {case.budget_usd}) would be exceeded."
            )
        spent_today = session.execute(
            select(
                func.coalesce(func.sum(func.coalesce(ProviderCall.cost_usd, ProviderCall.reserved_usd)), 0)
            ).where(ProviderCall.usage_day == day)
        ).scalar_one()
        if Decimal(spent_today) + amount > s.daily_budget_usd:
            raise BudgetExceeded(
                "DAILY_BUDGET", f"The daily model budget (USD {s.daily_budget_usd}) would be exceeded."
            )
        call = ProviderCall(
            org_id=ctx.org_id,
            case_id=ctx.case_id,
            run_id=ctx.run_id,
            purpose=purpose,
            model=s.model_name,
            location=s.model_location,
            status="reserved",
            reserved_usd=amount,
            usage_day=day,
        )
        session.add(call)
        case.cost_reserved_usd = Decimal(case.cost_reserved_usd) + amount
        session.flush()
        call_id = call.id
    ctx.model_calls += 1
    return call_id


def settle(
    ctx: RunContext,
    call_id: uuid.UUID,
    *,
    status: str,
    usage: Any | None,
    latency_ms: int,
    error_code: str | None = None,
    search_queries: int = 0,
) -> None:
    with org_session(ctx.org_id) as session:
        call = session.get(ProviderCall, call_id)
        case = session.execute(select(Case).where(Case.id == ctx.case_id).with_for_update()).scalar_one()
        call.status = status
        call.latency_ms = latency_ms
        call.error_code = error_code
        if usage is not None and getattr(usage, "prompt_token_count", None) is not None:
            prompt = int(usage.prompt_token_count or 0)
            output = int(usage.candidates_token_count or 0)
            thinking = int(getattr(usage, "thoughts_token_count", 0) or 0)
            cost = actual_cost(prompt, output + thinking)
            cost += get_settings().search_price_per_query * search_queries
            call.input_tokens, call.output_tokens, call.thinking_tokens, call.cost_usd = (
                prompt,
                output,
                thinking,
                cost,
            )
            case.cost_reserved_usd = Decimal(case.cost_reserved_usd) - Decimal(call.reserved_usd) + cost
            case.cost_actual_usd = Decimal(case.cost_actual_usd) + cost
            ctx.input_tokens += prompt
            ctx.output_tokens += output + thinking
            ctx.cost_usd += cost
        elif status == "error" and error_code in ("INJECTED_TIMEOUT", "INJECTED_QUOTA"):
            # A refused request made no provider call; release the reservation.
            case.cost_reserved_usd = Decimal(case.cost_reserved_usd) - Decimal(call.reserved_usd)
            call.cost_usd = Decimal("0")
        # Otherwise usage is unknown: the conservative reservation stays.


def injected_fault(ctx: RunContext) -> str | None:
    """Demonstration fault injection, set by an environment administrator and labelled as such."""
    with org_session(ctx.org_id) as session:
        control = session.execute(
            select(OrgControl).where(OrgControl.org_id == ctx.org_id).with_for_update()
        ).scalar_one_or_none()
        if control and control.model_fault and control.model_fault_remaining > 0:
            control.model_fault_remaining -= 1
            fault = control.model_fault
            if control.model_fault_remaining == 0:
                control.model_fault = None
            return fault
    return None


def classify(exc: BaseException) -> str | None:
    """Return a transient error code, or None if the error is not retryable."""
    text = f"{type(exc).__name__} {exc}"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "Timeout" in text or "timed out" in text:
        return "TIMEOUT"
    for code in ("429", "RESOURCE_EXHAUSTED"):
        if code in text:
            return "QUOTA"
    for code in (
        "500",
        "502",
        "503",
        "504",
        "UNAVAILABLE",
        "INTERNAL",
        "ConnectError",
        "RemoteProtocolError",
    ):
        if code in text:
            return "UNAVAILABLE"
    return None


async def guarded_call(
    ctx: RunContext,
    purpose: str,
    est_input_tokens: int,
    call,
    *,
    search: bool = False,
    output_tokens: int | None = None,
    timeout_s: float | None = None,
):
    """Run `call()` (an awaitable factory) under reservation, deadline and bounded transient retries."""
    s = get_settings()
    attempt = 0
    while True:
        call_id = reserve(ctx, purpose, est_input_tokens, search=search, output_tokens=output_tokens)
        started = time.monotonic()
        try:
            fault = injected_fault(ctx)
            if fault:
                raise TransientModelError("INJECTED_TIMEOUT" if fault == "timeout" else "INJECTED_QUOTA")
            timeout = max(1.0, min(timeout_s or s.model_timeout_s, ctx.time_left() - 1))
            async with asyncio.timeout(timeout):
                response, usage = await call()
            settle(
                ctx,
                call_id,
                status="ok",
                usage=usage,
                latency_ms=int((time.monotonic() - started) * 1000),
                search_queries=search_query_count(response) if search else 0,
            )
            return response
        except BudgetExceeded:
            raise
        except Exception as exc:
            code = exc.code if isinstance(exc, TransientModelError) else classify(exc)
            settle(
                ctx,
                call_id,
                status="error",
                usage=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_code=code or type(exc).__name__,
            )
            if code is None:
                raise ModelUnavailable("MODEL_ERROR", f"The model call failed: {type(exc).__name__}") from exc
            if (
                attempt >= ctx.limit("transient_retries", s.max_transient_retries)
                or ctx.model_calls >= ctx.limit("model_calls_per_invocation", s.max_model_calls)
                or ctx.time_left() < 5
            ):
                raise ModelUnavailable(
                    code, f"The model service is unavailable ({code}) after {attempt + 1} attempt(s)."
                ) from exc
            attempt += 1
            ctx.retries += 1
            await asyncio.sleep(min(2.0 * attempt, 4.0))


async def generate_json(
    ctx: RunContext,
    purpose: str,
    system: str,
    prompt: str,
    schema: Any,
    *,
    images: list[bytes] | None = None,
    output_tokens: int | None = None,
    timeout_s: float | None = None,
) -> Any:
    """Nested structured call (e.g. compare_statements) through the same gateway and allowances."""
    s = get_settings()
    client = vertex_client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=output_tokens or s.max_output_tokens,
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=s.thinking_level),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    async def call():
        # Keep the provider's deadline aligned with the remaining invocation time.
        # A larger local timeout alone still leaves the SDK's default deadline in force.
        if timeout_s is not None:
            remaining = max(1.0, min(timeout_s, ctx.time_left() - 1))
            config.http_options = types.HttpOptions(timeout=int(remaining * 1000))
        response = await client.aio.models.generate_content(
            model=s.model_name,
            contents=types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
                + [types.Part.from_bytes(data=image, mime_type="image/png") for image in images],
            )
            if images
            else prompt,
            config=config,
        )
        return response, response.usage_metadata

    return await guarded_call(
        ctx,
        purpose,
        estimate_tokens(len(system) + len(prompt)) + 2048 * len(images or []),
        call,
        output_tokens=output_tokens,
        timeout_s=timeout_s,
    )


def search_query_count(response: Any) -> int:
    """Billing estimate from returned queries, retaining the allowance when usage is absent."""
    metadata = next((c.grounding_metadata for c in response.candidates or [] if c.grounding_metadata), None)
    queries = getattr(metadata, "web_search_queries", None)
    return len(queries) if queries else get_settings().search_reserve_queries


async def generate_grounded(ctx: RunContext, system: str, prompt: str) -> Any:
    s = get_settings()
    client = vertex_client()
    timeout_s = 45.0
    output_tokens = 4096

    async def call():
        response = await client.aio.models.generate_content(
            model=s.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                max_output_tokens=output_tokens,
                http_options=types.HttpOptions(
                    timeout=int(max(1.0, min(timeout_s, ctx.time_left() - 1)) * 1000)
                ),
                temperature=1,
                thinking_config=types.ThinkingConfig(thinking_level=s.thinking_level),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return response, response.usage_metadata

    return await guarded_call(
        ctx,
        "credit_public_search",
        estimate_tokens(len(system) + len(prompt)),
        call,
        search=True,
        output_tokens=output_tokens,
        timeout_s=timeout_s,
    )
