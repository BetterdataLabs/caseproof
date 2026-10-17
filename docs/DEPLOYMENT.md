# Google Cloud deployment

This guide deploys CaseProof to Cloud Run with Cloud SQL, Cloud Storage and Cloud Tasks. The public web uses an access-code gate; the API and worker stay private. Run the steps in order from the repository root using Bash. For local startup, use the [README](../README.md#run-locally).

The local app and container builds have been verified. A hosted end-to-end deployment has not yet been verified; complete step 8 before sharing a hosted demo.

## Services

| Component               | Deployment                                                           |
| ----------------------- | -------------------------------------------------------------------- |
| Web                     | Next.js container on Cloud Run, gated by an access code                     |
| API                     | Private Cloud Run service using the backend image with `ROLE=api`    |
| Worker                  | Private Cloud Run service using the backend image with `ROLE=worker` |
| Database                | Cloud SQL for PostgreSQL 17                                          |
| Documents and summaries | Private Cloud Storage bucket                                         |
| Delivery                | Cloud Tasks invokes `POST /jobs/execute` on the worker               |
| Reconciliation          | Cloud Scheduler invokes `POST /jobs/reconcile` every minute          |
| Migration and seed      | One-off Cloud Run jobs using the backend image                       |

Cloud Tasks and scheduled reconciliation replace the local dispatcher process. The web forwards browser cookies to the private API and authenticates to Cloud Run with its own service identity. Demo users do not need Google accounts.

## 1. Prepare the project

Install an up-to-date [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), Docker with Buildx, Python 3 and the PostgreSQL `psql` client. Use a billing-enabled Google Cloud project. The operator needs permission to create the listed resources, manage IAM, enable services, access secrets and act as the deployment service accounts. Confirm Vertex AI access to the configured Gemini model.

Set your deployment values. Keep this shell open for the remaining steps. Replace the project ID. The access code is entered privately in step 3.

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export REGION="asia-southeast1"
export SQL_INSTANCE="caseproof-db"
export REGISTRY="caseproof"
export BUCKET="${PROJECT_ID}-caseproof-objects"
export QUEUE="caseproof-jobs"
export RELEASE="v1"

gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  cloudtasks.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com

export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
export TASK_SA="caseproof-tasks@${PROJECT_ID}.iam.gserviceaccount.com"
export BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY}/backend:${RELEASE}"
export WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY}/web:${RELEASE}"

for name in web api worker migrate tasks; do
  gcloud iam service-accounts create "caseproof-${name}" \
    --display-name="CaseProof ${name}"
done
```

The resources below are billed to this project, including Cloud SQL while the app is idle. Choose a region available to Cloud Run, SQL, Tasks and Scheduler; the model uses Vertex AI's global endpoint independently.

## 2. Create storage, the task queue and database

```bash
gcloud artifacts repositories create "$REGISTRY" \
  --repository-format=docker --location="$REGION"

gcloud storage buckets create "gs://${BUCKET}" \
  --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://${BUCKET}" --public-access-prevention

gcloud tasks queues create "$QUEUE" --location="$REGION" \
  --max-concurrent-dispatches=8 --max-dispatches-per-second=8
```

Generate initial database passwords and connection files inside the ignored local data directory. Run this only for the first deployment; keep these files for the subsequent secret-upload step.

```bash
mkdir -p .data/deploy
chmod 700 .data/deploy
python3 - <<'PY'
import os
import secrets
from pathlib import Path

folder = Path(".data/deploy")
def save(name, value):
    with (folder / name).open("x") as target:
        target.write(value)
    (folder / name).chmod(0o600)

passwords = {role: secrets.token_hex(24) for role in
             ("postgres", "cp_owner", "cp_app", "cp_dispatcher")}
for role, password in passwords.items():
    save(f"{role}-password", password)
for role in ("cp_owner", "cp_app", "cp_dispatcher"):
    save(f"{role}-url", f"postgresql+psycopg://{role}:{passwords[role]}"
         f"@/caseproof?host=/cloudsql/{os.environ['SQL_CONNECTION']}")
save("session-secret", secrets.token_hex(32))
runtime_sql = Path("infra/gcp/sql/roles.sql").read_text()
runtime_sql = runtime_sql.replace("REPLACE_APP_PASSWORD", passwords["cp_app"])
runtime_sql = runtime_sql.replace("REPLACE_DISPATCHER_PASSWORD", passwords["cp_dispatcher"])
owner_sql = (
    f"CREATE ROLE cp_owner LOGIN PASSWORD '{passwords['cp_owner']}' "
    "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;\n"
    "GRANT cp_owner TO postgres;\n"
    "ALTER DATABASE caseproof OWNER TO cp_owner;\n"
    "GRANT ALL ON SCHEMA public TO cp_owner;\n"
)
save("bootstrap.sql", owner_sql + runtime_sql)
PY

gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_17 --edition=ENTERPRISE \
  --region="$REGION" --cpu=2 --memory=8GiB \
  --availability-type=zonal --storage-size=20GB \
  --assign-ip --backup-start-time=03:00 \
  --root-password="$(cat .data/deploy/postgres-password)"

gcloud sql databases create caseproof --instance="$SQL_INSTANCE"
gcloud sql connect "$SQL_INSTANCE" --user=postgres --database=caseproof
```

When prompted, use the generated password in `.data/deploy/postgres-password`. At the `psql` prompt, apply the generated SQL, then exit:

```sql
\set ON_ERROR_STOP on
\i .data/deploy/bootstrap.sql
\q
```

This creates the owner and the two restricted runtime roles before migrations. The database uses a public IP with Cloud SQL connector authentication; the Cloud Run services attach its Unix socket. The interactive connect command temporarily authorizes your workstation IP. This example uses a zonal database for a demo; use regional availability if the deployment needs database failover.

## 3. Store secrets and grant runtime permissions

Upload each connection string and the session signing secret to Secret Manager:

```bash
for role in cp_owner cp_app cp_dispatcher; do
  gcloud secrets create "caseproof-${role}-url" \
    --replication-policy=automatic --data-file=".data/deploy/${role}-url"
done
gcloud secrets create caseproof-session-secret \
  --replication-policy=automatic --data-file=.data/deploy/session-secret

printf 'Demo access code (it will not be saved in the repo): '
read -rs DEMO_ACCESS_CODE
printf '\n'
printf '%s' "$DEMO_ACCESS_CODE" | gcloud secrets create caseproof-demo-access-code \
  --replication-policy=automatic --data-file=-
unset DEMO_ACCESS_CODE
```

Use the same value as `CASEPROOF_DEMO_ACCESS_CODE` in the local `.env`. Compose and Cloud Run then show the same access-code screen.

Grant database connectivity to the backend identities, and storage/task access to the runtime services:

```bash
for name in api worker migrate; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:caseproof-${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role=roles/cloudsql.client --condition=None
done

for name in api worker; do
  member="serviceAccount:caseproof-${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="$member" --role=roles/storage.objectUser
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$member" --role=roles/cloudtasks.enqueuer --condition=None
  gcloud iam service-accounts add-iam-policy-binding "$TASK_SA" \
    --member="$member" --role=roles/iam.serviceAccountUser
  gcloud secrets add-iam-policy-binding caseproof-cp_app-url \
    --member="$member" --role=roles/secretmanager.secretAccessor
done

gcloud secrets add-iam-policy-binding caseproof-cp_dispatcher-url \
  --member="serviceAccount:caseproof-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding caseproof-cp_owner-url \
  --member="serviceAccount:caseproof-migrate@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding caseproof-session-secret \
  --member="serviceAccount:caseproof-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding caseproof-demo-access-code \
  --member="serviceAccount:caseproof-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

for role in roles/aiplatform.user roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:caseproof-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role" --condition=None
done
```

Create the Google-managed service identities used for delivery, and ensure the task and scheduler service agents retain their service-agent roles:

```bash
for service in cloudtasks.googleapis.com cloudscheduler.googleapis.com; do
  gcloud beta services identity create --service="$service" --project="$PROJECT_ID"
done

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com" \
  --role=roles/cloudtasks.serviceAgent --condition=None
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --role=roles/cloudscheduler.serviceAgent --condition=None
```

The deployer also needs permission to act as `caseproof-tasks` when creating the Scheduler job. Runtime services receive only their needed connection secrets; the database owner URL is reserved for migration and seed jobs.

## 4. Build and publish the images

Use the **repository root** as the Docker build context. Both images target Linux AMD64 for Cloud Run.

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"

docker buildx build --platform linux/amd64 \
  -f services/backend/Dockerfile -t "$BACKEND_IMAGE" --push .
docker buildx build --platform linux/amd64 \
  -f apps/web/Dockerfile -t "$WEB_IMAGE" --push .
```

The backend image includes policies and the saved Evaluation report. The web image includes the downloadable sample documents. Both images run as non-root users and listen on port 8080.

## 5. Run migrations and seed memberships

Deploy and execute the migration job. Wait for success before seeding:

```bash
gcloud run jobs deploy caseproof-migrate \
  --image="$BACKEND_IMAGE" --region="$REGION" \
  --service-account="caseproof-migrate@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="$SQL_CONNECTION" \
  --set-env-vars="ROLE=migrate,CASEPROOF_ENVIRONMENT=cloud,CASEPROOF_DEV_IDENTITY=false" \
  --set-secrets="CASEPROOF_MIGRATION_URL=caseproof-cp_owner-url:1,CASEPROOF_OWNER_DATABASE_URL=caseproof-cp_owner-url:1" \
  --tasks=1 --max-retries=0 --task-timeout=300s \
  --execute-now --wait
```

Create an environment file for the seed job. This creates the existing Alex, Sam and Aisha memberships:

```bash
python3 - <<'PY'
import json
from pathlib import Path

Path(".data/deploy/seed.json").write_text(json.dumps({
    "ROLE": "seed",
    "CASEPROOF_ENVIRONMENT": "cloud",
    "CASEPROOF_DEV_IDENTITY": "false",
    "SEED_ARGS": "",
}, indent=2))
PY

gcloud run jobs deploy caseproof-seed \
  --image="$BACKEND_IMAGE" --region="$REGION" \
  --service-account="caseproof-migrate@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="$SQL_CONNECTION" \
  --env-vars-file=.data/deploy/seed.json \
  --set-secrets="CASEPROOF_OWNER_DATABASE_URL=caseproof-cp_owner-url:1" \
  --tasks=1 --max-retries=0 --task-timeout=300s \
  --execute-now --wait
```

Seeding adds missing identities and policy; it preserves existing cases and memberships. The three visible accounts are Alex, Sam and Aisha. The access code is configured on the API, independently of seeding.

## 6. Deploy the worker and API

Create the worker environment file:

```bash
cat > .data/deploy/worker.yaml <<EOF
ROLE: "worker"
CASEPROOF_ENVIRONMENT: "cloud"
CASEPROOF_DEV_IDENTITY: "false"
CASEPROOF_DEMO_MODE: "true"
CASEPROOF_ALLOW_COMPOSED_MESSAGES: "true"
CASEPROOF_GCP_PROJECT: "${PROJECT_ID}"
CASEPROOF_MODEL_NAME: "gemini-3.8-flash"
CASEPROOF_MODEL_LOCATION: "global"
CASEPROOF_STORAGE_BACKEND: "gcs"
CASEPROOF_GCS_BUCKET: "${BUCKET}"
CASEPROOF_QUEUE_BACKEND: "cloudtasks"
CASEPROOF_CLOUD_TASKS_QUEUE: "projects/${PROJECT_ID}/locations/${REGION}/queues/${QUEUE}"
CASEPROOF_CLOUD_TASKS_SERVICE_ACCOUNT: "${TASK_SA}"
CASEPROOF_DB_POOL_SIZE: "2"
CASEPROOF_DB_MAX_OVERFLOW: "1"
EOF

gcloud run deploy caseproof-worker \
  --image="$BACKEND_IMAGE" --region="$REGION" \
  --service-account="caseproof-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="$SQL_CONNECTION" \
  --env-vars-file=.data/deploy/worker.yaml \
  --set-secrets="CASEPROOF_DATABASE_URL=caseproof-cp_app-url:1,CASEPROOF_DISPATCHER_DATABASE_URL=caseproof-cp_dispatcher-url:1" \
  --port=8080 --cpu=1 --memory=1Gi \
  --concurrency=1 --min=0 --max=8 --timeout=300 \
  --no-allow-unauthenticated

export WORKER_URL="$(gcloud run services describe caseproof-worker \
  --region="$REGION" --format='value(status.url)')"

printf 'CASEPROOF_WORKER_URL: "%s"\n' "$WORKER_URL" >> .data/deploy/worker.yaml
gcloud run services update caseproof-worker --region="$REGION" \
  --env-vars-file=.data/deploy/worker.yaml

gcloud run services add-iam-policy-binding caseproof-worker \
  --region="$REGION" --member="serviceAccount:${TASK_SA}" \
  --role=roles/run.invoker
```

The first deployment obtains the worker's stable service URL. The immediate update configures that same URL as its expected task-token audience before any jobs are submitted.

Create the API environment by reusing the shared configuration and turning on the seeded personas behind the access code:

```bash
cp .data/deploy/worker.yaml .data/deploy/api.yaml
python3 - <<'PY'
from pathlib import Path

path = Path(".data/deploy/api.yaml")
text = path.read_text().replace('ROLE: "worker"', 'ROLE: "api"')
text = text.replace('CASEPROOF_DEV_IDENTITY: "false"', 'CASEPROOF_DEV_IDENTITY: "true"')
path.write_text(text)
PY

gcloud run deploy caseproof-api \
  --image="$BACKEND_IMAGE" --region="$REGION" \
  --service-account="caseproof-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="$SQL_CONNECTION" \
  --env-vars-file=.data/deploy/api.yaml \
  --set-secrets="CASEPROOF_DATABASE_URL=caseproof-cp_app-url:1,CASEPROOF_SESSION_SECRET=caseproof-session-secret:1,CASEPROOF_DEMO_ACCESS_CODE=caseproof-demo-access-code:1" \
  --port=8080 --cpu=1 --memory=1Gi \
  --concurrency=20 --min=0 --max=4 --timeout=300 \
  --no-allow-unauthenticated

gcloud run services add-iam-policy-binding caseproof-api \
  --region="$REGION" \
  --member="serviceAccount:caseproof-web@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/run.invoker

export API_URL="$(gcloud run services describe caseproof-api \
  --region="$REGION" --format='value(status.url)')"
```

The services use IAM authentication while retaining default network ingress so the web and task delivery can reach their Cloud Run URLs. Database pool and service instance limits are starting values for a demo; they are not measured capacity.

## 7. Deploy the web service and enable sign-in

```bash
cat > .data/deploy/web.yaml <<EOF
CASEPROOF_API_URL: "${API_URL}"
CASEPROOF_API_AUDIENCE: "${API_URL}"
EOF

gcloud run deploy caseproof-web \
  --image="$WEB_IMAGE" --region="$REGION" \
  --service-account="caseproof-web@${PROJECT_ID}.iam.gserviceaccount.com" \
  --env-vars-file=.data/deploy/web.yaml \
  --port=8080 --cpu=1 --memory=512Mi \
  --concurrency=40 --min=0 --max=4 --timeout=300 \
  --allow-unauthenticated

export WEB_URL="$(gcloud run services describe caseproof-web \
  --region="$REGION" --format='value(status.url)')"

printf 'CASEPROOF_ALLOWED_ORIGINS: "%s"\n' "$WEB_URL" >> .data/deploy/api.yaml
gcloud run services update caseproof-api --region="$REGION" \
  --env-vars-file=.data/deploy/api.yaml
```

The web hostname is public. The access code is the gate. Share that code with demo users privately. Do not commit it.

Two configuration values have distinct purposes:

| Value                                  | Required setting                                     |
| -------------------------------------- | ---------------------------------------------------- |
| Private API Cloud Run URL              | Web `CASEPROOF_API_URL` and `CASEPROOF_API_AUDIENCE` |
| Browser origin, with no trailing slash | API `CASEPROOF_ALLOWED_ORIGINS`                      |

Changing a browser hostname also requires updating the API's allowed origins. The API refuses to boot if development identities are on and the access-code secret is empty.

## 8. Start reconciliation and verify the app

```bash
gcloud scheduler jobs create http caseproof-reconcile \
  --location="$REGION" --schedule="* * * * *" --time-zone=Etc/UTC \
  --uri="${WORKER_URL}/jobs/reconcile" --http-method=POST \
  --oidc-service-account-email="$TASK_SA" \
  --oidc-token-audience="$WORKER_URL" \
  --headers="Content-Type=application/json" --message-body='{}' \
  --attempt-deadline=300s

gcloud scheduler jobs run caseproof-reconcile --location="$REGION"
gcloud run services logs read caseproof-worker --region="$REGION" --limit=30
```

The Scheduler request must use the **same service-account email and audience** as Cloud Tasks. The worker validates both.

Open the URL returned by:

```bash
gcloud run services describe caseproof-web \
  --region="$REGION" --format='value(status.url)'
```

Complete these checks before sharing that URL:

1. Enter the configured access code. Alex opens the bank queue. Use **Switch persona** to select Sam or Aisha and verify the vendor and read-only workspaces.
2. As the vendor, submit the [sample invoice and receipt](../apps/web/public/sample-documents/caseproof-upload-example.zip). Confirm processing starts and a missing-evidence request appears.
3. Upload the corrected invoice and remaining receipt. As the reviewer, inspect the completed checklist and download PDF and JSON summaries.
4. Confirm original documents remain downloadable after a service revision or restart.
5. Inspect **Operations**, the Cloud Tasks queue and Scheduler execution logs for successful delivery and reconciliation.
6. Use the [demo verification guide](TESTING.md) to check policy changes, decisions, document checks and optional research.

## Troubleshooting

| Symptom                                             | Check                                                                                                                             |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Access code is rejected                             | Secret `caseproof-demo-access-code` on the API, and `CASEPROOF_DEV_IDENTITY=true` only on the API                                  |
| API refuses to start                                | Cloud with development identities requires the access-code secret. The worker keeps development identities off                    |
| Sign-in stays on the code form                      | Web is public, the unlock cookie is HttpOnly, and the API allowed origin matches the browser URL                                  |
| Web receives 403 from the API                       | Web service identity has Cloud Run Invoker on the API and uses its service URL as audience                                        |
| Changes fail origin validation                      | API allowed origins exactly match the browser's scheme and hostname                                                               |
| Database connection fails                           | Cloud SQL attachment, client role, secret version, database passwords and migrations                                              |
| Jobs stay queued                                    | Queue resource name, enqueue/act-as permissions, worker URL and Scheduler execution                                               |
| Worker rejects a task or Scheduler call             | OIDC audience is the worker base URL; token email matches the configured task service account; that account can invoke the worker |
| Model or research fails                             | Worker Vertex permissions, model availability, project quotas and the case's remaining budget                                     |
| Uploads or downloads fail                           | Bucket name and object access for the API and worker identities                                                                   |

Read application logs with:

```bash
gcloud run services logs read caseproof-api --region="$REGION" --limit=50
gcloud run services logs read caseproof-worker --region="$REGION" --limit=50
gcloud run services logs read caseproof-web --region="$REGION" --limit=50
```

## Update an existing deployment

1. Set a new `RELEASE` and rebuild the two image variables from step 1, then build and push as in step 4.
2. Take a database backup with `gcloud sql backups create --instance="$SQL_INSTANCE"`.
3. Deploy and execute the migration job with the new backend image. Wait for it to succeed.
4. Update the worker, API and web images. Existing service configuration and identities remain attached:

```bash
gcloud run services update caseproof-worker --region="$REGION" --image="$BACKEND_IMAGE"
gcloud run services update caseproof-api --region="$REGION" --image="$BACKEND_IMAGE"
gcloud run services update caseproof-web --region="$REGION" --image="$WEB_IMAGE"
```

5. Repeat the hosted workflow checks. Seed only when adding missing memberships; do not recreate resources or generate replacement database passwords during a normal update.

Secret references in this guide pin version `1`. For rotation, add a new Secret Manager version and explicitly update the affected Cloud Run services or jobs. Keep the session secret consistent across API instances. Preserve Cloud SQL backups and Cloud Storage objects when retiring services if you need the saved cases.

## Current limits

- Hosted deployment, task replay and backup restoration still need verification in the target project. Load capacity has not been measured.
- Automatic document checks support the subset described in the README. Appearance review covers at most three pages and does not authenticate issuers or signatures.
- Public company research supplies a sourced brief for bank review; it is not calibrated credit scoring or lending approval.
- Customer requests and replies stay within the app; external email or messaging delivery is not implemented.
- Retention fields exist, but scheduled object and record cleanup is not implemented.

Defaults and additional configuration are defined in [config.py](../services/backend/src/caseproof/config.py). Case budgets, model token prices and search cost estimates should match the project's chosen model and current provider pricing.
