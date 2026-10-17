#!/bin/bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:?}"
REGION="${REGION:?}"
BACKEND_IMAGE="${BACKEND_IMAGE:?}"
WEB_IMAGE="${WEB_IMAGE:?}"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
cd "$REPO_ROOT"

docker buildx build --platform linux/amd64 \
  -f services/backend/Dockerfile -t "$BACKEND_IMAGE" --push .

docker buildx build --platform linux/amd64 \
  -f apps/web/Dockerfile -t "$WEB_IMAGE" --push .
