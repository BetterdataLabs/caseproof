locals {
  shared_env = {
    CASEPROOF_ENVIRONMENT                 = "cloud"
    CASEPROOF_DEMO_MODE                   = "true"
    CASEPROOF_ALLOW_COMPOSED_MESSAGES     = "true"
    CASEPROOF_GCP_PROJECT                 = local.project
    CASEPROOF_MODEL_NAME                  = var.model_name
    CASEPROOF_MODEL_LOCATION              = var.model_location
    CASEPROOF_STORAGE_BACKEND             = "gcs"
    CASEPROOF_GCS_BUCKET                  = google_storage_bucket.objects.name
    CASEPROOF_QUEUE_BACKEND               = "cloudtasks"
    CASEPROOF_CLOUD_TASKS_QUEUE           = "projects/${local.project}/locations/${var.region}/queues/${google_cloud_tasks_queue.jobs.name}"
    CASEPROOF_CLOUD_TASKS_SERVICE_ACCOUNT = local.sa["tasks"]
    CASEPROOF_DB_POOL_SIZE                = "2"
    CASEPROOF_DB_MAX_OVERFLOW             = "1"
    CASEPROOF_DAILY_BUDGET_USD            = var.daily_model_budget_usd
    CASEPROOF_CASE_BUDGET_USD             = var.case_model_budget_usd
  }
}

resource "google_cloud_run_v2_job" "migrate" {
  project  = local.project
  name     = "caseproof-migrate"
  location = var.region

  template {
    template {
      service_account = local.sa["migrate"]
      timeout         = "300s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.this.connection_name]
        }
      }
      containers {
        image = local.backend_image
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name  = "ROLE"
          value = "migrate"
        }
        env {
          name  = "CASEPROOF_ENVIRONMENT"
          value = "cloud"
        }
        env {
          name  = "CASEPROOF_DEV_IDENTITY"
          value = "false"
        }
        env {
          name = "CASEPROOF_MIGRATION_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this["caseproof-cp_owner-url"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "CASEPROOF_OWNER_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this["caseproof-cp_owner-url"].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    terraform_data.images,
    terraform_data.sql_grants,
    google_secret_manager_secret_iam_member.migrate,
    google_project_iam_member.sql_client,
  ]

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_job" "seed" {
  project  = local.project
  name     = "caseproof-seed"
  location = var.region

  template {
    template {
      service_account = local.sa["migrate"]
      timeout         = "300s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.this.connection_name]
        }
      }
      containers {
        image = local.backend_image
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name  = "ROLE"
          value = "seed"
        }
        env {
          name  = "CASEPROOF_ENVIRONMENT"
          value = "cloud"
        }
        env {
          name  = "CASEPROOF_DEV_IDENTITY"
          value = "false"
        }
        env {
          name  = "CASEPROOF_STORAGE_BACKEND"
          value = "gcs"
        }
        env {
          name  = "CASEPROOF_GCS_BUCKET"
          value = google_storage_bucket.objects.name
        }
        env {
          name = "CASEPROOF_OWNER_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this["caseproof-cp_owner-url"].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_cloud_run_v2_job.migrate]

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_job" "stop" {
  project  = local.project
  name     = "caseproof-stop"
  location = var.region

  template {
    template {
      service_account = local.sa["stop"]
      timeout         = "180s"
      max_retries     = 1
      containers {
        image   = "gcr.io/google.com/cloudsdktool/google-cloud-cli:slim"
        command = ["bash", "-c"]
        args = [
          <<-EOT
          set -euo pipefail
          gcloud sql instances patch caseproof-db --project=${local.project} --activation-policy=NEVER --quiet
          for svc in caseproof-web caseproof-api caseproof-worker; do
            gcloud run services update "$svc" --project=${local.project} --region=${var.region} --max-instances=0 --quiet || true
          done
          EOT
        ]
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  depends_on = [google_project_iam_member.stop]
}

resource "terraform_data" "migrate" {
  depends_on = [google_cloud_run_v2_job.migrate]
  triggers_replace = {
    job   = google_cloud_run_v2_job.migrate.id
    image = local.backend_image
  }
  provisioner "local-exec" {
    command = "gcloud run jobs execute caseproof-migrate --project=${local.project} --region=${var.region} --wait"
  }
}

resource "terraform_data" "owner_rls" {
  depends_on = [terraform_data.migrate]
  triggers_replace = {
    migrate = terraform_data.migrate.id
  }
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "${path.module}/scripts/owner_rls.sh"
    environment = {
      CONNECTION_NAME   = google_sql_database_instance.this.connection_name
      POSTGRES_PASSWORD = random_password.sql["postgres"].result
      PROXY_DIR         = "${path.module}/../../../.data/deploy/terraform"
    }
  }
}

resource "terraform_data" "seed" {
  depends_on = [
    terraform_data.migrate,
    terraform_data.owner_rls,
    google_cloud_run_v2_job.seed,
    google_storage_bucket_iam_member.objects,
  ]
  triggers_replace = {
    job = google_cloud_run_v2_job.seed.id
  }
  provisioner "local-exec" {
    command = "gcloud run jobs execute caseproof-seed --project=${local.project} --region=${var.region} --wait"
  }
}

resource "google_cloud_run_v2_service" "worker" {
  project  = local.project
  name     = "caseproof-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = local.sa["worker"]
    timeout                          = "300s"
    max_instance_request_concurrency = 1
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.this.connection_name]
      }
    }
    containers {
      image = local.backend_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env {
        name  = "ROLE"
        value = "worker"
      }
      env {
        name  = "CASEPROOF_DEV_IDENTITY"
        value = "false"
      }
      dynamic "env" {
        for_each = local.shared_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "CASEPROOF_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["caseproof-cp_app-url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CASEPROOF_DISPATCHER_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["caseproof-cp_dispatcher-url"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    terraform_data.seed,
    google_secret_manager_secret_iam_member.worker,
  ]

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "terraform_data" "worker_url" {
  depends_on = [google_cloud_run_v2_service.worker]
  triggers_replace = {
    uri = google_cloud_run_v2_service.worker.uri
  }
  provisioner "local-exec" {
    command = "gcloud run services update caseproof-worker --project=${local.project} --region=${var.region} --update-env-vars=CASEPROOF_WORKER_URL=${google_cloud_run_v2_service.worker.uri}"
  }
}

resource "google_cloud_run_v2_service" "api" {
  project  = local.project
  name     = "caseproof-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = local.sa["api"]
    timeout                          = "300s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.this.connection_name]
      }
    }
    containers {
      image = local.backend_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env {
        name  = "ROLE"
        value = "api"
      }
      env {
        name  = "CASEPROOF_DEV_IDENTITY"
        value = "true"
      }
      dynamic "env" {
        for_each = local.shared_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "CASEPROOF_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["caseproof-cp_app-url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CASEPROOF_SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["caseproof-session-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CASEPROOF_DEMO_ACCESS_CODE"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["caseproof-demo-access-code"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    terraform_data.seed,
    google_secret_manager_secret_iam_member.api,
  ]

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_service" "web" {
  project  = local.project
  name     = "caseproof-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = local.sa["web"]
    timeout                          = "300s"
    max_instance_request_concurrency = 40
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }
    containers {
      image = local.web_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "CASEPROOF_API_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "CASEPROOF_API_AUDIENCE"
        value = google_cloud_run_v2_service.api.uri
      }
    }
  }

  depends_on = [terraform_data.images]

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "terraform_data" "api_origin" {
  depends_on = [
    google_cloud_run_v2_service.web,
    google_cloud_run_v2_service.api,
    google_cloud_run_v2_service.worker,
  ]
  triggers_replace = {
    origin     = google_cloud_run_v2_service.web.uri
    regional   = "https://caseproof-web-${local.number}.${var.region}.run.app"
    worker     = google_cloud_run_v2_service.worker.uri
    api_gen    = google_cloud_run_v2_service.api.generation
    worker_gen = google_cloud_run_v2_service.worker.generation
  }
  provisioner "local-exec" {
    command = "gcloud run services update caseproof-api --project=${local.project} --region=${var.region} --update-env-vars='^|^CASEPROOF_ALLOWED_ORIGINS=https://caseproof-web-${local.number}.${var.region}.run.app,${google_cloud_run_v2_service.web.uri}|CASEPROOF_WORKER_URL=${google_cloud_run_v2_service.worker.uri}'"
  }
}

resource "terraform_data" "health" {
  depends_on = [
    terraform_data.api_origin,
    terraform_data.worker_url,
    google_cloud_run_v2_service_iam_member.web_public,
  ]
  triggers_replace = {
    url = google_cloud_run_v2_service.web.uri
  }
  provisioner "local-exec" {
    command = "curl --fail --retry 12 --retry-all-errors --retry-delay 8 --silent --show-error ${google_cloud_run_v2_service.web.uri}/ >/dev/null"
  }
}
