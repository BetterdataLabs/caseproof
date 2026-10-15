"""Separate case creation from vendor portal access.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("vendor_contact_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_cases_vendor_contact", "cases", "users", ["vendor_contact_id"], ["id"])
    op.create_index("ix_cases_vendor_contact_id", "cases", ["vendor_contact_id"])
    op.execute("""
        UPDATE cases c SET vendor_contact_id = c.created_by
        FROM memberships m
        WHERE m.user_id = c.created_by AND m.org_id = c.org_id
          AND m.roles @> ARRAY['vendor']::varchar[]
    """)


def downgrade() -> None:
    op.drop_index("ix_cases_vendor_contact_id", table_name="cases")
    op.drop_constraint("fk_cases_vendor_contact", "cases", type_="foreignkey")
    op.drop_column("cases", "vendor_contact_id")
