# CaseProof

CaseProof is an invoice-financing document review app built with Gemini and Google ADK. Vendors submit invoices and receipts, the agent requests missing evidence, and bank reviewers resolve questions and download PDF or JSON summaries.

The app includes a vendor portal, bank review workspace, read-only access, configurable review policies, optional document appearance checks, public company research, and automation controls. It uses Next.js, FastAPI and PostgreSQL. Gemini runs on Vertex AI.

## Run locally

### 1. Install the prerequisites

- Docker with Compose v2.24 or later, with the Docker daemon running
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- A billing-enabled Google Cloud project with Vertex AI access

Docker builds the Python backend and the production web app. You do not need Python or Node.js installed on your machine. The commands below use Bash on Linux, macOS or Windows through WSL.

### 2. Get the app and configure the project

```bash
git clone https://github.com/BetterdataLabs/bfsi-aibuildercup2026.git
cd bfsi-aibuildercup2026
test -f .env || cp .env.example .env
```

If you already have the repository, run the configuration command from its root. Edit `.env` and replace the project placeholder:

```dotenv
CASEPROOF_GCP_PROJECT=YOUR_PROJECT_ID
CASEPROOF_MODEL_NAME=gemini-3.8-flash
CASEPROOF_MODEL_LOCATION=global
# Optional locally; use the same access code as the Cloud Run API secret.
CASEPROOF_DEMO_ACCESS_CODE=
```

The configured model must be available to your project. Keep the other values from `.env.example` for the local demo.

### 3. Authenticate with Google Cloud

Create credentials inside the repository's ignored local data directory:

```bash
export CLOUDSDK_CONFIG="$PWD/.data/gcloud"
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Your account needs **Vertex AI User** and **Service Usage Consumer** access. Enabling the API also requires permission to enable services; skip that command if it is already enabled. Model calls and optional Google Search grounding are billed to the configured project.

If you already have an Application Default Credentials or service-account file, set `GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/credentials.json` in `.env` instead. Setup makes a protected copy available to the worker; credentials are not included in the images or Git repository.

### 4. Start the app

From the repository root:

```bash
docker compose up --build --detach --wait
```

The first build downloads dependencies and takes longer. Compose starts PostgreSQL, applies migrations, seeds the demo accounts and policy, then runs the API, worker, dispatcher and production web server. It waits for the database, API, worker and web health checks before returning.

Open **http://localhost:3400**. If an access code is configured in `.env`, enter it to open Alex's bank queue; **Switch persona** selects Sam or Aisha. With an empty local access code, the three-account picker opens directly. The services run in the background; no terminals need to stay open. Port 3400 must be available.

### 5. Check, stop or update the app

Check service status and follow the logs:

```bash
docker compose ps --all
docker compose logs --follow api worker dispatcher web
```

The `initialize` container should show **Exited (0)** after successful setup. The other services stay running. Press **Ctrl+C** to stop following logs; this leaves the app running.

Stop the app:

```bash
docker compose down
```

Database records, uploaded documents and credentials are stored in named Docker volumes and survive this command. Start again with the same startup command. Do not add `--volumes` unless you intend to delete the saved local workspace.

After pulling an update or changing `.env`, apply it with:

```bash
docker compose up --build --detach --wait
```

The setup step preserves existing cases. Services restart automatically after a process failure while Docker is running. This Compose configuration is for a local demo and publishes only the web port on loopback. For a hosted app with the access-code gate, follow [Deploy to Google Cloud](#deploy-to-google-cloud).

For editing the application with live reload, use the optional [development guide](docs/DEVELOPMENT.md).

## Review workflow

Use **Switch persona** to follow one case across the three workspaces:

| Persona                | Available actions                                                    |
| ---------------------- | -------------------------------------------------------------------- |
| **Sam Lim — Vendor**   | Submit documents, read bank requests and supply corrections          |
| **Alex Chen — Bank**   | Review cases, resolve decisions, edit policies and manage automation |
| **Aisha Tan — Viewer** | Read cases, documents and completed summaries                        |

Download and extract the [sample document pack](apps/web/public/sample-documents/caseproof-upload-example.zip):

1. As **Sam**, create a submission with **01-invoice.pdf** and **02-first-receipt.pdf**.
2. Switch to **Alex**. After processing, inspect the incorrect invoice total and missing delivery evidence.
3. As **Sam**, open the request and upload **03-corrected-invoice.pdf** as an updated invoice.
4. After processing finishes, upload **04-remaining-receipt.pdf** as a receipt for another delivery.
5. As **Alex**, inspect the completed review and download its PDF or JSON summary. **Aisha** can view the same case.

Explore the remaining features from the bank workspace:

| Feature                    | How to try it                                                                                                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Reviewer decisions         | Send a written reply disputing a receipt, then review the resulting task as Alex.                                                                                              |
| Document appearance checks | Enable the optional checks when creating a case and, if available, upload reference templates.                                                                                 |
| Company credit research    | Select the buyer or seller and its registration country when uploading a case. Use an identifiable real company to explore public sources; the sample companies are fictional. |
| Policy                     | Add or edit review criteria, publish a version, then use **Apply policy** on an existing case.                                                                                 |
| Operations                 | Inspect runs, pause or resume automation, and use the recovery controls.                                                                                                       |
| Evaluation                 | Open the saved comparison report and inspect its recorded outcomes.                                                                                                            |
| Demo scenarios             | Open **New case → Demo scenarios**, or **Your documents → Browse the scenario library** for downloadable PDFs and walkthroughs.                                                |

Uploaded documents are reviewed with Gemini using source citations and exact calculation tools. PDFs, scans, PNG/JPEG/TIFF/WebP images, DOCX, XLSX, CSV and text files are supported, including multiple items, decimal quantities, different currencies, taxes, discounts and other charges. Unreadable content or unresolved ambiguity is identified for review. See [Document review](docs/DOCUMENT_REVIEW.md) for the processing flow and limits. Appearance findings and public company research support review; they do not authenticate documents or approve financing.

## Deploy to Google Cloud

Follow the [complete deployment guide](docs/DEPLOYMENT.md) in order. It includes the commands, configuration values and account setup for each step:

1. [Configure the project and service accounts](docs/DEPLOYMENT.md#1-prepare-the-project).
2. [Create storage, the task queue and PostgreSQL roles](docs/DEPLOYMENT.md#2-create-storage-the-task-queue-and-database).
3. [Store connection secrets and grant runtime permissions](docs/DEPLOYMENT.md#3-store-secrets-and-grant-runtime-permissions).
4. [Build and publish both container images](docs/DEPLOYMENT.md#4-build-and-publish-the-images).
5. [Run migrations and create application memberships](docs/DEPLOYMENT.md#5-run-migrations-and-seed-memberships).
6. [Deploy the private worker and API](docs/DEPLOYMENT.md#6-deploy-the-worker-and-api).
7. [Deploy the web service and configure access-code sign-in](docs/DEPLOYMENT.md#7-deploy-the-web-service-and-enable-sign-in).
8. [Schedule reconciliation and verify the hosted workflow](docs/DEPLOYMENT.md#8-start-reconciliation-and-verify-the-app).

Cloud Run hosts the three services; Cloud SQL and a private Cloud Storage bucket persist data. Cloud Tasks and Cloud Scheduler replace the local dispatcher. Hosted demo users enter an access code, then use the same Alex, Sam and Aisha accounts. Store the code in Secret Manager and bind it to `CASEPROOF_DEMO_ACCESS_CODE` on the API, with `CASEPROOF_DEV_IDENTITY=true`. The worker keeps development identities off. The private API still requires the web service’s Cloud Run identity token.

The local startup path has been verified. The cloud guide is based on the included adapters and current Google Cloud commands; a hosted end-to-end deployment has not yet been verified.

## Troubleshooting

| Symptom                                 | Action                                                                                                                                                          |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Startup cannot find the credential file | Complete the Google authentication step or set an existing file's absolute path in `GOOGLE_APPLICATION_CREDENTIALS`.                                            |
| Setup exits with an error               | Run `docker compose logs initialize database`. Check the database and credential setup, then rerun the startup command.                                         |
| Port 3400 is already in use             | Stop the application already using that port before starting CaseProof.                                                                                         |
| Case stays queued                       | Run `docker compose ps` and inspect `docker compose logs worker dispatcher`.                                                                                    |
| Model access fails                      | Check the project, model availability, credentials and Vertex AI permissions. Rerun the startup command after changing configuration or refreshing credentials. |
| Sam cannot see a bank-created case      | Select Sam as its **Vendor contact**.                                                                                                                           |

## Documentation

The [documentation index](docs/README.md) links the architecture, deployment, company research and demo verification guides. Original documents, the presentation PDF and historical reports are preserved in [docs/archive/](docs/archive/README.md).
