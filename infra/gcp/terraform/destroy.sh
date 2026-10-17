#!/bin/bash
# Tear down CaseProof resources created by this module.
# Does not close a billing account. Deletes the GCP project only if you
# created it with create_project=true and project_deletion_policy=DELETE.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ "${DESTROY_CONFIRM:-}" != "yes" ]]; then
  echo "This destroys Cloud Run, Cloud SQL, secrets and related resources" >&2
  echo "in the project from infra/gcp/terraform/terraform.tfvars." >&2
  echo "Re-run with DESTROY_CONFIRM=yes to proceed." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env (needed only to satisfy the access-code variable)." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

export TF_DATA_DIR="$ROOT/.data/deploy/terraform/plugins"
cd "$HERE"
terraform destroy -input=false -auto-approve \
  -var="demo_access_code=${CASEPROOF_DEMO_ACCESS_CODE:-unused}"
