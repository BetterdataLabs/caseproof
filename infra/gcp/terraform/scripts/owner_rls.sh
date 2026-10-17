#!/bin/bash
# Cloud SQL cannot grant BYPASSRLS. FORCE ROW LEVEL SECURITY still applies to
# cp_owner, so seed and other owner writes need an explicit allow-all policy.
set -euo pipefail

PROXY_DIR="${PROXY_DIR:?}"
CONNECTION_NAME="${CONNECTION_NAME:?}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?}"
mkdir -p "$PROXY_DIR"

arch="$(uname -m)"
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$arch" in
  arm64|aarch64) arch="arm64" ;;
  x86_64) arch="amd64" ;;
esac

proxy="$PROXY_DIR/cloud-sql-proxy"
if [[ ! -x "$proxy" ]]; then
  curl -fsSL -o "$proxy" \
    "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.15.2/cloud-sql-proxy.${os}.${arch}"
  chmod +x "$proxy"
fi

"$proxy" --port 15433 "$CONNECTION_NAME" &
proxy_pid=$!
trap 'kill "$proxy_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p 15433 -U postgres -d caseproof -c 'select 1' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p 15433 -U postgres -d caseproof -v ON_ERROR_STOP=1 <<'SQL'
SET ROLE cp_owner;
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'policy_versions',
    'org_controls',
    'cases',
    'questions',
    'documents',
    'document_versions',
    'facts',
    'observations',
    'material_claims',
    'requests',
    'request_items',
    'replies',
    'human_tasks',
    'decisions',
    'jobs',
    'outbox',
    'agent_runs',
    'agent_actions',
    'provider_calls',
    'audit_events',
    'command_receipts',
    'exports'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS owner_all ON %I', t);
    EXECUTE format(
      'CREATE POLICY owner_all ON %I TO cp_owner USING (true) WITH CHECK (true)',
      t
    );
  END LOOP;
END $$;
SQL
