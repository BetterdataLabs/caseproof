"""Optional, case-scoped public company research.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases", sa.Column("credit_research", postgresql.JSONB(), nullable=False, server_default="{}")
    )


def downgrade() -> None:
    op.drop_column("cases", "credit_research")
