"""Database engines and organisation-scoped transactions.

Runtime roles (cp_app, cp_dispatcher) are non-superusers without BYPASSRLS. Every organisation-scoped
transaction sets `app.org_id` locally; PostgreSQL row policies then reject rows from other organisations
even if an application query forgets a filter.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


@lru_cache
def _engine(url: str) -> Engine:
    s = get_settings()
    return create_engine(
        url,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_timeout=5,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=5000"},
    )


def app_engine() -> Engine:
    return _engine(get_settings().database_url)


def dispatcher_engine() -> Engine:
    return _engine(get_settings().dispatcher_database_url)


def owner_engine() -> Engine:
    return _engine(get_settings().owner_database_url)


_factories: dict[str, sessionmaker[Session]] = {}


def _factory(engine: Engine) -> sessionmaker[Session]:
    key = str(engine.url)
    if key not in _factories:
        _factories[key] = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)
    return _factories[key]


@contextmanager
def org_session(org_id: uuid.UUID, engine: Engine | None = None) -> Iterator[Session]:
    """One transaction scoped to one organisation. Commits on success, rolls back on error."""
    session = _factory(engine or app_engine())()
    try:
        session.execute(text("SELECT set_config('app.org_id', :org, true)"), {"org": str(org_id)})
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def global_session(engine: Engine | None = None) -> Iterator[Session]:
    """A transaction without organisation context: identity lookups, job routing and reconciliation."""
    session = _factory(engine or app_engine())()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
