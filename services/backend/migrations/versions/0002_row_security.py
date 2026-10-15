"""Row-level security, runtime grants and append-only history.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

from caseproof.models import ORG_SCOPED_TABLES

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

GLOBAL_READ = ["organisations", "users", "memberships", "purge_records"]
APPEND_ONLY = ["audit_events"]


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO cp_app, cp_dispatcher")
    for table in GLOBAL_READ:
        op.execute(f"GRANT SELECT ON {table} TO cp_app, cp_dispatcher")
    for table in ORG_SCOPED_TABLES:
        if table in APPEND_ONLY:
            op.execute(f"GRANT SELECT, INSERT ON {table} TO cp_app, cp_dispatcher")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO cp_app, cp_dispatcher")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY org_isolation ON {table} "
            f"USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            f"WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cp_app, cp_dispatcher")
    # Command receipts are deleted only by the privileged retention job.
    op.execute("REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM cp_app, cp_dispatcher")

    # The dispatcher routes and recovers work across organisations. It sees only job metadata,
    # outbox rows (ids, never content) and the timer columns it needs; effects run org-scoped.
    for table in ["jobs", "outbox"]:
        op.execute(f"CREATE POLICY dispatcher_routing ON {table} TO cp_dispatcher USING (true) WITH CHECK (true)")
    for table in ["requests", "human_tasks", "cases"]:
        op.execute(f"CREATE POLICY dispatcher_timers ON {table} FOR SELECT TO cp_dispatcher USING (true)")

    # A worker receives only a job id. This definer function reveals the owning organisation of an
    # active job and nothing else, so the worker can establish its organisation context.
    op.execute(
        """
        CREATE FUNCTION cp_job_route(p_job uuid) RETURNS TABLE(org_id uuid, case_id uuid, kind text, state text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
        $$ SELECT j.org_id, j.case_id, j.kind::text, j.state::text FROM jobs j WHERE j.id = p_job $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION cp_job_route(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION cp_job_route(uuid) TO cp_app, cp_dispatcher")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS cp_job_route(uuid)")
    for table in ["requests", "human_tasks", "cases"]:
        op.execute(f"DROP POLICY IF EXISTS dispatcher_timers ON {table}")
    for table in ["jobs", "outbox"]:
        op.execute(f"DROP POLICY IF EXISTS dispatcher_routing ON {table}")
    for table in ORG_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
