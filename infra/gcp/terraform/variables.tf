variable "project_id" {
  type        = string
  description = "Google Cloud project that will host CaseProof. Create it first unless create_project is true."

  validation {
    condition     = var.project_id != "" && var.project_id != "your-gcp-project-id"
    error_message = "Set project_id in terraform.tfvars to your Google Cloud project."
  }
}

variable "project_name" {
  type        = string
  default     = "CaseProof"
  description = "Display name used only when Terraform creates the project."
}

variable "create_project" {
  type        = bool
  default     = false
  description = "When true, Terraform creates project_id and links billing_account. Most operators should leave this false and use an existing project."
}

variable "project_deletion_policy" {
  type        = string
  default     = "PREVENT"
  description = "PREVENT keeps the GCP project on destroy. Set DELETE only if you created the project with this module and want destroy to remove it."
}

variable "billing_account" {
  type        = string
  default     = ""
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX). Required when create_project or enable_budget is true. Never commit a real value."
  sensitive   = true
}

variable "quota_project" {
  type        = string
  default     = ""
  description = "Existing project used for API quota during provider calls. Defaults to project_id. Set this to an already-active project if create_project is true."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region for Cloud Run, Cloud SQL, Artifact Registry, Cloud Tasks and Scheduler."
}

variable "environment" {
  type        = string
  default     = "demo"
  description = "Label applied to created resources. Use demo, staging or production."
}

variable "demo_access_code" {
  type        = string
  sensitive   = true
  description = "Public-site gate. Pass from .env via apply.sh. Never commit this value."
}

variable "release" {
  type        = string
  default     = "v1"
  description = "Container image tag. Change this and re-apply to rebuild and roll images from your laptop."
}

variable "model_name" {
  type        = string
  default     = "gemini-3.8-flash"
  description = "Vertex AI Gemini model the worker calls."
}

variable "model_location" {
  type        = string
  default     = "global"
  description = "Vertex AI location for the model."
}

variable "daily_model_budget_usd" {
  type        = string
  default     = "5"
  description = "In-app daily Vertex reserve. This is application config, not a Google Cloud quota."
}

variable "case_model_budget_usd" {
  type        = string
  default     = "0.50"
  description = "In-app per-case Vertex reserve."
}

variable "cloud_run_min_instances" {
  type        = number
  default     = 0
  description = "Minimum Cloud Run instances for web, API and worker. 0 scales to zero."
}

variable "cloud_run_max_instances" {
  type        = number
  default     = 2
  description = "Maximum Cloud Run instances for web, API and worker."
}

variable "sql_tier" {
  type        = string
  default     = "db-f1-micro"
  description = "Cloud SQL machine type. db-f1-micro is the cheapest starting point."
}

variable "sql_disk_gb" {
  type        = number
  default     = 10
  description = "Cloud SQL SSD size in GB."
}

variable "sql_deletion_protection" {
  type        = bool
  default     = false
  description = "Set true for a long-lived environment so Terraform cannot delete the instance."
}

variable "sql_availability_type" {
  type        = string
  default     = "ZONAL"
  description = "ZONAL is cheaper. REGIONAL adds a standby in another zone."
}

variable "task_max_concurrent" {
  type        = number
  default     = 8
  description = "Cloud Tasks concurrent dispatches."
}

variable "enable_budget" {
  type        = bool
  default     = false
  description = "Create a monthly billing alert on this project. Emails billing admins; it does not stop spend."
}

variable "budget_amount" {
  type        = number
  default     = 100
  description = "Monthly budget alert amount when enable_budget is true."
}

variable "budget_currency" {
  type        = string
  default     = "USD"
  description = "ISO currency for the optional budget alert, for example USD or SGD."
}

variable "stop_cron" {
  type        = string
  default     = ""
  description = "Optional Cloud Scheduler cron that pauses SQL and sets Cloud Run max instances to 0. Empty skips the schedule. Example: 0 0 1 1 *"
}

variable "stop_timezone" {
  type        = string
  default     = "Etc/UTC"
  description = "Time zone for stop_cron."
}
