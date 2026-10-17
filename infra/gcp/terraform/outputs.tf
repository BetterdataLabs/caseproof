output "project_id" {
  value = local.project
}

output "web_url" {
  description = "Public CaseProof URL. The access code is the gate."
  value       = google_cloud_run_v2_service.web.uri
}

output "api_url" {
  description = "Private API URL. Browser traffic goes through the web service."
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_url" {
  description = "Private worker URL. Invoked by Cloud Tasks and Scheduler."
  value       = google_cloud_run_v2_service.worker.uri
}

output "region" {
  value = var.region
}

output "sql_connection" {
  value = google_sql_database_instance.this.connection_name
}

output "artifact_registry" {
  value = google_artifact_registry_repository.images.id
}
