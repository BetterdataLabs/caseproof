resource "google_storage_bucket" "objects" {
  project                     = local.project
  name                        = "${local.project}-caseproof-objects"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = false
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "objects" {
  for_each = toset(["api", "worker", "migrate"])
  bucket   = google_storage_bucket.objects.name
  role     = "roles/storage.objectUser"
  member   = "serviceAccount:${local.sa[each.value]}"
}

resource "google_cloud_tasks_queue" "jobs" {
  project  = local.project
  name     = "caseproof-jobs"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = var.task_max_concurrent
    max_dispatches_per_second = var.task_max_concurrent
  }

  retry_config {
    max_attempts = 8
  }

  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "images" {
  project       = local.project
  location      = var.region
  repository_id = "caseproof"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

locals {
  backend_image = "${var.region}-docker.pkg.dev/${local.project}/caseproof/backend:${var.release}"
  web_image     = "${var.region}-docker.pkg.dev/${local.project}/caseproof/web:${var.release}"
}

resource "terraform_data" "images" {
  depends_on = [google_artifact_registry_repository.images]

  triggers_replace = {
    release = var.release
    repo    = google_artifact_registry_repository.images.id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "${path.module}/scripts/build_images.sh"
    environment = {
      PROJECT       = local.project
      REGION        = var.region
      BACKEND_IMAGE = local.backend_image
      WEB_IMAGE     = local.web_image
      REPO_ROOT     = "${path.module}/../../.."
    }
  }
}
