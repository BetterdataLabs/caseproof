terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.47"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.47"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  backend "local" {
    path = "../../../.data/deploy/terraform/terraform.tfstate"
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = coalesce(var.quota_project, var.project_id)
  default_labels = {
    app        = "caseproof"
    env        = var.environment
    managed-by = "terraform"
  }
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = coalesce(var.quota_project, var.project_id)
  default_labels = {
    app        = "caseproof"
    env        = var.environment
    managed-by = "terraform"
  }
}
