resource "google_sql_database_instance" "this" {
  project             = local.project
  name                = "caseproof-db"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = var.sql_deletion_protection

  settings {
    tier              = var.sql_tier
    edition           = "ENTERPRISE"
    availability_type = var.sql_availability_type
    disk_size         = var.sql_disk_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = false

    backup_configuration {
      enabled = var.sql_availability_type == "REGIONAL"
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "off"
    }
  }

  root_password = random_password.sql["postgres"].result

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "caseproof" {
  project  = local.project
  name     = "caseproof"
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "postgres" {
  project  = local.project
  instance = google_sql_database_instance.this.name
  name     = "postgres"
  password = random_password.sql["postgres"].result
}

resource "google_sql_user" "roles" {
  for_each = {
    cp_owner      = random_password.sql["owner"].result
    cp_app        = random_password.sql["app"].result
    cp_dispatcher = random_password.sql["dispatcher"].result
  }
  project  = local.project
  instance = google_sql_database_instance.this.name
  name     = each.key
  password = each.value
}

resource "terraform_data" "sql_grants" {
  depends_on = [
    google_sql_database.caseproof,
    google_sql_user.postgres,
    google_sql_user.roles,
  ]

  triggers_replace = {
    instance = google_sql_database_instance.this.connection_name
    owner    = google_sql_user.roles["cp_owner"].name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "${path.module}/scripts/bootstrap_sql.sh"
    environment = {
      PROJECT           = local.project
      REGION            = var.region
      INSTANCE          = google_sql_database_instance.this.name
      CONNECTION_NAME   = google_sql_database_instance.this.connection_name
      POSTGRES_PASSWORD = random_password.sql["postgres"].result
      PROXY_DIR         = "${path.module}/../../../.data/deploy/terraform"
    }
  }
}
