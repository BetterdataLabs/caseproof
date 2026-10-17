# Deploy CaseProof with Terraform

This module builds a self-contained Google Cloud demo: public Cloud Run web, private API and worker, Cloud SQL, Cloud Storage, Cloud Tasks, Secret Manager and a reconcile schedule. Runtime service accounts have no JSON keys. State and plugins stay in gitignored `.data/deploy/terraform/`.

Do not put project IDs, billing account IDs, access codes, or live hostnames into git. Copy `terraform.tfvars.example` to `terraform.tfvars` on your machine.

The same architecture is documented as individual `gcloud` steps in [docs/DEPLOYMENT.md](../../../docs/DEPLOYMENT.md).

## What you get

| Component | Resource |
| --- | --- |
| Web | Cloud Run `caseproof-web`, public invoker, access-code gate |
| API | Cloud Run `caseproof-api`, invoker is the web service account only |
| Worker | Cloud Run `caseproof-worker`, invoker is the tasks service account |
| Database | Cloud SQL PostgreSQL 17, Cloud SQL connector (no authorized networks) |
| Files | Private Cloud Storage bucket |
| Jobs | Cloud Tasks queue plus Scheduler reconcile every minute |
| Secrets | DB URLs, session secret, access code |
| Images | Artifact Registry `caseproof` (`backend` and `web`) |

## Prerequisites

- Terraform >= 1.8
- Docker with Buildx (linux/amd64 image builds)
- `gcloud` (`gcloud auth login` and `gcloud auth application-default login`)
- `psql` (used once for SQL grants)
- A billing-enabled Google Cloud project with permission to enable APIs, create Cloud Run, Cloud SQL and IAM
- Vertex AI access to the Gemini model you configure
- Repo-root `.env` with `CASEPROOF_DEMO_ACCESS_CODE` set (gitignored)

Create the GCP project in the console unless you explicitly set `create_project = true`.

## Configure

```bash
cp infra/gcp/terraform/terraform.tfvars.example infra/gcp/terraform/terraform.tfvars
```

Edit `terraform.tfvars`. The only required value is `project_id`. Keep that file local.

| Variable | Default | Purpose |
| --- | --- | --- |
| `project_id` | *(required)* | Existing GCP project. |
| `region` | `us-central1` | Cloud Run, SQL, registry, tasks, scheduler. |
| `environment` | `demo` | Resource label. |
| `create_project` | `false` | Create `project_id` and attach `billing_account`. |
| `billing_account` | empty | Needed only for project creation or a budget alert. |
| `quota_project` | `project_id` | Existing project for API quota if you are creating a new one. |
| `demo_access_code` | from `.env` | Public-site gate. Sensitive. Passed by `apply.sh`. |
| `release` | `v1` | Image tag. Change it to rebuild from your laptop. |
| `model_name` | `gemini-3.8-flash` | Vertex model. |
| `cloud_run_min_instances` | `0` | Scale to zero when idle. |
| `cloud_run_max_instances` | `2` | Upper bound per service. |
| `sql_tier` | `db-f1-micro` | Cheapest SQL starting point. Always-on cost. |
| `enable_budget` | `false` | Monthly **email** alert. Does not stop spend. |
| `stop_cron` | empty | Optional pause schedule. Empty means none. |

Set `CASEPROOF_GCP_PROJECT` in `.env` to the same project so local Compose and Vertex use the same model project if you also run locally.

## Deploy

From the repository root:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
./infra/gcp/terraform/apply.sh
```

The script:

1. Reads `CASEPROOF_DEMO_ACCESS_CODE` from `.env` (not from tfvars).
2. Enables the required APIs.
3. Creates SQL, the objects bucket, the task queue, Artifact Registry and secrets.
4. Builds and pushes `backend` and `web` for `var.release`.
5. Runs migrate, owner row-security policies and seed.
6. Deploys Cloud Run web, API and worker.
7. Schedules reconcile every minute.
8. Prints the public URL.

The first SQL instance takes about 10–15 minutes. Re-run the same command after you change Terraform or `release`.

Open only the web URL. Enter the access code, then use the demo accounts from the project README. Direct calls to the API or worker return 403 without a service-account identity token.

## Maintain

| Task | How |
| --- | --- |
| See URLs | `cd infra/gcp/terraform && TF_DATA_DIR=../../../.data/deploy/terraform/plugins terraform output` |
| Change the access code | Update `.env`, then re-run `apply.sh`. Secret Manager gets a new version. |
| Roll application code | Bump `release` in `terraform.tfvars` and re-apply, **or** run the [Cloud Build pipeline](#continuous-deploy) so images update without rewriting env vars. |
| Apply schema changes | `gcloud run jobs execute caseproof-migrate --region=REGION --wait` |
| Reseed demo users | `gcloud run jobs execute caseproof-seed --region=REGION --wait` |
| Reset demo data | `gcloud run jobs execute caseproof-seed --update-env-vars=SEED_ARGS=--reset --region=REGION --wait` then delete leftover objects in the bucket if needed |
| Pause (stop spend from compute) | `gcloud run jobs execute caseproof-stop --region=REGION --wait` — SQL `NEVER`, Cloud Run max instances 0 |
| Resume | `gcloud sql instances patch caseproof-db --activation-policy=ALWAYS` and set Cloud Run `--max-instances` back (or re-apply) |
| Rotate session secret | `terraform taint random_password.session` then re-apply (signs everyone out) |

Terraform ignores Cloud Run **image** changes after the first apply so a later image-only roll does not reset env vars. A full apply still refreshes allowed origins when the web URL changes.

## Continuous deploy

`cloudbuild.yaml` at the repository root rebuilds both images, runs migrate and updates Cloud Run **images only**. It contains no project IDs or credentials.

Create a trigger in Cloud Build (GitHub app or Cloud Build repository connection) on the branch you want:

- Config file: `cloudbuild.yaml`
- Substitutions: `_REGION` = the region in `terraform.tfvars`, `_TAG` = `$SHORT_SHA` or `latest`
- Service account: create one with Artifact Registry Writer, Cloud Run Developer, Cloud SQL Client and `iam.serviceAccountUser` on the CaseProof runtime accounts

Do not commit a GitHub token or webhook secret. Prefer the Cloud Build GitHub app over a personal access token.

## Scale

| Resource | Default | How to change |
| --- | --- | --- |
| Cloud Run web / API / worker | min 0, max 2 | `cloud_run_min_instances` / `cloud_run_max_instances`, then re-apply, or `gcloud run services update SERVICE --min-instances=N --max-instances=N` |
| Cloud SQL | `db-f1-micro`, 10 GB, zonal | `sql_tier`, `sql_disk_gb`, `sql_availability_type`. SQL does not scale to zero. |
| Vertex | app daily US$5, US$0.50 / case | `daily_model_budget_usd` and `case_model_budget_usd`. Not a GCP quota. |
| Cloud Tasks | 8 concurrent | `task_max_concurrent` |
| Reconcile | every minute | `scheduler.tf` |

SQL is the meter that keeps running when Cloud Run is at zero. Pause with `caseproof-stop`, or destroy, to stop that bill. Stopped SQL still bills disk and the assigned IPv4.

For more traffic, raise max instances first. Move SQL off `db-f1-micro` before you expect concurrent reviewers. Set `sql_availability_type = "REGIONAL"` and `sql_deletion_protection = true` if the environment must survive a zone outage.

## Spend controls

An optional budget (`enable_budget = true`) emails billing-account admins at 50 / 80 / 100% of `budget_amount`. Google Cloud budgets are alerts. They do not disable billing or stop SQL.

The `caseproof-stop` job is a manual (or scheduled) pause. It does not unlink billing, delete the project, or cancel the reconcile job. `destroy.sh` is the clean teardown.

Typical cost drivers, cheapest first: Cloud SQL, Vertex usage, Artifact Registry storage, Cloud Run while serving, Cloud Scheduler.

## Security

| Control | Behaviour |
| --- | --- |
| Public surface | Only `caseproof-web` has `allUsers` invoker. |
| API | Invoker is `caseproof-web@` only. |
| Worker | Invoker is `caseproof-tasks@`. The app also checks the Cloud Tasks OIDC email. |
| Access code | HttpOnly Secure cookie. Compared in constant time. Stored in Secret Manager, not in git. |
| Identities | Six runtime service accounts. No user-managed JSON keys. |
| Secrets | Per-secret accessors. Owner DB URL is migrate/seed only. Worker is the only `aiplatform.user`. |
| Storage | Uniform bucket ACL, public access prevention. |
| SQL | Public IPv4, **no authorized networks**. Ordinary `psql` from the internet is refused. Cloud Run uses the Cloud SQL connector Unix socket. Private IP was skipped to avoid an always-on VPC connector. |
| Cookies / CSRF | Session and demo-gate cookies are HttpOnly, Secure, SameSite=Lax. Mutating API calls require CSRF and an idempotency key. |

Residual risk you should accept before sharing a demo URL:

- A leaked access code unlocks the public site.
- OpenAPI is reachable through the web proxy at `/api/v1/docs` (mutating routes still need the gate, session and CSRF).
- Unlock rate-limit is in-memory per API instance.
- The default Compute Engine service account is not used here; review project-level IAM separately.

## Destroy

```bash
DESTROY_CONFIRM=yes ./infra/gcp/terraform/destroy.sh
```

Removes the resources this module created. The billing account stays open. The GCP project is deleted only if you set `create_project = true` and `project_deletion_policy = DELETE`.

After destroy, create a new project ID if you used `create_project` — project IDs are not immediately reusable.

## Remote state (optional)

The default backend is a local file under `.data/deploy/terraform/` (gitignored). For a shared team, change `versions.tf` to a Cloud Storage backend **before** the first apply, or migrate state with `terraform init -migrate-state`. Never commit `terraform.tfstate`.

## Layout

| Path | Role |
| --- | --- |
| `apply.sh` / `destroy.sh` | One-command apply and teardown from the repo root. |
| `terraform.tfvars.example` | Operator template. Copy, do not commit the real file. |
| `project.tf` | APIs, optional project create. |
| `iam.tf` | Runtime service accounts and invokers. |
| `sql.tf` / `scripts/bootstrap_sql.sh` | Cloud SQL and first grants. |
| `scripts/owner_rls.sh` | Owner policies required because Cloud SQL cannot grant `BYPASSRLS`. |
| `secrets.tf` | Passwords, DB URLs, session secret, access code. |
| `storage.tf` / `scripts/build_images.sh` | Bucket, queue, registry, image build. |
| `run.tf` | Migrate, seed, pause job, web / API / worker. |
| `scheduler.tf` | Reconcile and optional pause schedule. |
| `budget.tf` | Optional monthly alert. |
| `outputs.tf` | `web_url`, `api_url`, `project_id`, `sql_connection`. |
| `../../../cloudbuild.yaml` | Optional image rebuild pipeline. |
