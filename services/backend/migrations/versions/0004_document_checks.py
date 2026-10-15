"""Optional document appearance checks and immutable case reference selections.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases", sa.Column("document_checks", postgresql.JSONB(), nullable=False, server_default="{}")
    )
    op.add_column("document_versions", sa.Column("visual_review", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_versions", "visual_review")
    op.drop_column("cases", "document_checks")
