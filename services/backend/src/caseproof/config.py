"""Environment configuration and default operating limits."""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parents[4]  # .../app


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CASEPROOF_", env_file=str(APP_ROOT / ".env"), extra="ignore"
    )

    environment: str = "development"  # development | cloud
    dev_identity: bool = True  # seeded personas, loopback only; refused when environment=cloud
    demo_mode: bool = True  # simulated customer exchange and demo clock
    allow_composed_messages: bool = True  # private evaluation lane: simulation operator may type a message

    database_url: str = "postgresql+psycopg://cp_app:cp_app_local@127.0.0.1:56542/caseproof"
    dispatcher_database_url: str = (
        "postgresql+psycopg://cp_dispatcher:cp_dispatcher_local@127.0.0.1:56542/caseproof"
    )
    owner_database_url: str = "postgresql+psycopg://cp_owner:cp_owner_local@127.0.0.1:56542/caseproof"
    db_pool_size: int = 5
    db_max_overflow: int = 2

    storage_backend: str = "local"  # local | gcs
    storage_dir: Path = APP_ROOT / ".data" / "objects"
    gcs_bucket: str = ""

    session_secret: str = "local-development-only-session-secret-change-me"
    allowed_origins: str = "http://localhost:3400,http://127.0.0.1:3400"
    iap_audience: str = ""
    internal_token: str = "local-internal-token"  # worker/dispatcher auth in local mode
    max_command_bytes: int = 32 * 1024

    queue_backend: str = "local"  # local | cloudtasks
    worker_url: str = "http://127.0.0.1:8401"
    cloud_tasks_queue: str = ""
    cloud_tasks_service_account: str = ""

    # Model gateway
    model_provider: str = "vertex"  # vertex | rules (fixed-rule test and evaluation controller)
    gcp_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    model_location: str = "global"
    model_name: str = "gemini-3.8-flash"
    model_timeout_s: float = 25.0
    thinking_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    max_input_tokens: int = 20_000
    max_output_tokens: int = 2_048
    search_price_per_query: Decimal = Decimal("0.014")
    search_reserve_queries: int = 10  # allowance per grounded call; Google has no per-call query cap
    # Global Standard PayGo introductory pricing through 2026-12-31.
    # From 2027-01-01, configure input/output rates to 1.50/7.50 USD per million tokens.
    price_input_per_mtok: Decimal = Decimal("0.75")
    price_output_per_mtok: Decimal = Decimal("3.75")  # thinking tokens are billed as output

    # Invocation and case limits
    max_model_calls: int = 6
    max_tool_calls: int = 16
    max_active_seconds: float = 60.0
    max_transient_retries: int = 2
    max_wakeups: int = 12
    max_request_rounds: int = 2
    case_budget_usd: Decimal = Decimal("0.50")
    research_budget_usd: Decimal = Field(default=Decimal("1.00"), ge=Decimal("1.00"))
    daily_budget_usd: Decimal = Decimal("20.00")
    global_concurrency: int = 8
    org_concurrency: int = 2
    lease_seconds: int = 120
    heartbeat_seconds: int = 10
    claim_minutes: int = 15
    reminder_after_hours: int = 48
    stop_after_reminder_hours: int = 72
    reconcile_interval_s: float = 2.0  # local; Cloud Scheduler runs once per minute in cloud

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "cloud" and settings.dev_identity:
        raise RuntimeError("Refusing to start: development identities are enabled in a cloud environment.")
    return settings
