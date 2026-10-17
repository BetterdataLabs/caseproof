resource "random_password" "sql" {
  for_each = toset(["postgres", "owner", "app", "dispatcher"])
  length   = 28
  special  = false
}

resource "random_password" "session" {
  length  = 48
  special = false
}

locals {
  secret_values = {
    "caseproof-postgres-password" = random_password.sql["postgres"].result
    "caseproof-cp_owner-url"      = "postgresql+psycopg://cp_owner:${random_password.sql["owner"].result}@/caseproof?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
    "caseproof-cp_app-url"        = "postgresql+psycopg://cp_app:${random_password.sql["app"].result}@/caseproof?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
    "caseproof-cp_dispatcher-url" = "postgresql+psycopg://cp_dispatcher:${random_password.sql["dispatcher"].result}@/caseproof?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
    "caseproof-session-secret"    = random_password.session.result
    "caseproof-demo-access-code"  = var.demo_access_code
  }
}

resource "google_secret_manager_secret" "this" {
  for_each  = local.secret_values
  project   = local.project
  secret_id = each.key
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "this" {
  for_each    = local.secret_values
  secret      = google_secret_manager_secret.this[each.key].id
  secret_data = each.value
}

resource "google_secret_manager_secret_iam_member" "api" {
  for_each = toset([
    "caseproof-cp_app-url",
    "caseproof-session-secret",
    "caseproof-demo-access-code",
  ])
  project   = local.project
  secret_id = google_secret_manager_secret.this[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.sa["api"]}"
}

resource "google_secret_manager_secret_iam_member" "worker" {
  for_each = toset([
    "caseproof-cp_app-url",
    "caseproof-cp_dispatcher-url",
  ])
  project   = local.project
  secret_id = google_secret_manager_secret.this[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.sa["worker"]}"
}

resource "google_secret_manager_secret_iam_member" "migrate" {
  for_each = toset([
    "caseproof-cp_owner-url",
  ])
  project   = local.project
  secret_id = google_secret_manager_secret.this[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.sa["migrate"]}"
}
