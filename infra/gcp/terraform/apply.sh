#!/bin/bash
# Deploy CaseProof to the Google Cloud project in terraform.tfvars.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and set CASEPROOF_DEMO_ACCESS_CODE." >&2
  exit 1
fi

if [[ ! -f "$HERE/terraform.tfvars" ]]; then
  echo "Missing infra/gcp/terraform/terraform.tfvars." >&2
  echo "Copy terraform.tfvars.example and set your project_id (and region)." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${CASEPROOF_DEMO_ACCESS_CODE:-}" ]]; then
  echo "CASEPROOF_DEMO_ACCESS_CODE is empty in .env. Set a private value; do not commit it." >&2
  exit 1
fi

mkdir -p .data/deploy/terraform
export TF_DATA_DIR="$ROOT/.data/deploy/terraform/plugins"
chmod +x infra/gcp/terraform/scripts/*.sh

cd "$HERE"
terraform init -input=false
terraform apply -input=false -auto-approve \
  -var="demo_access_code=${CASEPROOF_DEMO_ACCESS_CODE}"

echo
echo "Public URL:"
terraform output -raw web_url
echo
