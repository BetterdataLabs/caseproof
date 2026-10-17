locals {
  runtime_accounts = {
    web     = "Serves the public Next.js site and invokes the API."
    api     = "Private FastAPI process."
    worker  = "Private agent worker."
    migrate = "One-off migrate and seed jobs."
    tasks   = "Cloud Tasks and Scheduler invoke the worker."
    stop    = "Optional pause job for SQL and Cloud Run."
  }
}

resource "google_service_account" "runtime" {
  for_each     = local.runtime_accounts
  project      = local.project
  account_id   = "caseproof-${each.key}"
  display_name = "CaseProof ${each.key}"
  description  = each.value
  depends_on   = [google_project_service.apis]
}

locals {
  sa = { for name, account in google_service_account.runtime : name => account.email }
}

resource "google_project_iam_member" "sql_client" {
  for_each = toset(["api", "worker", "migrate"])
  project  = local.project
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${local.sa[each.value]}"
}

resource "google_project_iam_member" "tasks_enqueuer" {
  for_each = toset(["api", "worker"])
  project  = local.project
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${local.sa[each.value]}"
}

resource "google_service_account_iam_member" "act_as_tasks" {
  for_each           = toset(["api", "worker"])
  service_account_id = google_service_account.runtime["tasks"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.sa[each.value]}"
}

resource "google_project_iam_member" "vertex_worker" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/serviceusage.serviceUsageConsumer",
  ])
  project = local.project
  role    = each.value
  member  = "serviceAccount:${local.sa["worker"]}"
}

resource "google_project_iam_member" "stop" {
  for_each = toset([
    "roles/cloudsql.editor",
    "roles/run.developer",
  ])
  project = local.project
  role    = each.value
  member  = "serviceAccount:${local.sa["stop"]}"
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  project  = local.project
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "api_web" {
  project  = local.project
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.sa["web"]}"
}

resource "google_cloud_run_v2_service_iam_member" "worker_tasks" {
  project  = local.project
  location = var.region
  name     = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.sa["tasks"]}"
}
