resource "google_cloud_scheduler_job" "reconcile" {
  project   = local.project
  name      = "caseproof-reconcile"
  region    = var.region
  schedule  = "* * * * *"
  time_zone = "Etc/UTC"

  http_target {
    uri         = "${google_cloud_run_v2_service.worker.uri}/jobs/reconcile"
    http_method = "POST"
    body        = base64encode("{}")
    headers = {
      Content-Type = "application/json"
    }
    oidc_token {
      service_account_email = local.sa["tasks"]
      audience              = google_cloud_run_v2_service.worker.uri
    }
  }

  attempt_deadline = "300s"
  depends_on = [
    terraform_data.worker_url,
    google_cloud_run_v2_service_iam_member.worker_tasks,
    google_project_service_identity.scheduler,
  ]
}

resource "google_cloud_scheduler_job" "stop" {
  count     = var.stop_cron != "" ? 1 : 0
  project   = local.project
  name      = "caseproof-stop"
  region    = var.region
  schedule  = var.stop_cron
  time_zone = var.stop_timezone

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${local.project}/jobs/caseproof-stop:run"
    http_method = "POST"
    body        = base64encode("{}")
    oauth_token {
      service_account_email = local.sa["stop"]
    }
  }

  depends_on = [
    google_cloud_run_v2_job.stop,
    google_project_service_identity.scheduler,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "stop_invoker" {
  project  = local.project
  location = var.region
  name     = google_cloud_run_v2_job.stop.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.sa["stop"]}"
}
