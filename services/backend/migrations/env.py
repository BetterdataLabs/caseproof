from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from caseproof.config import get_settings
from caseproof.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = os.environ.get("CASEPROOF_MIGRATION_URL") or get_settings().owner_database_url
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
