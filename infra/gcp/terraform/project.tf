data "google_project" "existing" {
  count      = var.create_project ? 0 : 1
  project_id = var.project_id
}

resource "google_project" "this" {
  count           = var.create_project ? 1 : 0
  name            = var.project_name
  project_id      = var.project_id
  billing_account = var.billing_account
  deletion_policy = var.project_deletion_policy

  labels = {
    app        = "caseproof"
    env        = var.environment
    managed-by = "terraform"
  }

  lifecycle {
    precondition {
      condition     = var.billing_account != ""
      error_message = "billing_account is required when create_project is true."
    }
  }
}

locals {
  project = var.create_project ? google_project.this[0].project_id : data.google_project.existing[0].project_id
  number  = var.create_project ? google_project.this[0].number : data.google_project.existing[0].number
  apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "cloudtasks.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "compute.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each                   = toset(local.apis)
  project                    = local.project
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

resource "google_project_service_identity" "tasks" {
  provider = google-beta
  project  = local.project
  service  = "cloudtasks.googleapis.com"
  depends_on = [
    google_project_service.apis["cloudtasks.googleapis.com"],
  ]
}

resource "google_project_service_identity" "scheduler" {
  provider = google-beta
  project  = local.project
  service  = "cloudscheduler.googleapis.com"
  depends_on = [
    google_project_service.apis["cloudscheduler.googleapis.com"],
  ]
}
