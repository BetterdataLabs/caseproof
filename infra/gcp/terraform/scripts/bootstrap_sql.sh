#!/bin/bash
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

"$proxy" --port 15432 "$CONNECTION_NAME" &
proxy_pid=$!
trap 'kill "$proxy_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p 15432 -U postgres -d caseproof -c 'select 1' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p 15432 -U postgres -d caseproof -v ON_ERROR_STOP=1 <<'SQL'
GRANT cp_owner TO postgres;
ALTER DATABASE caseproof OWNER TO cp_owner;
GRANT ALL ON SCHEMA public TO cp_owner;
GRANT CONNECT ON DATABASE caseproof TO cp_app, cp_dispatcher;
SQL
