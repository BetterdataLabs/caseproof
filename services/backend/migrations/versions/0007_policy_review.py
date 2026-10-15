"""Retain Gemini policy assessments against a specific evidence set.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases", sa.Column("policy_review", postgresql.JSONB(), nullable=False, server_default="{}")
    )


def downgrade() -> None:
    op.drop_column("cases", "policy_review")
