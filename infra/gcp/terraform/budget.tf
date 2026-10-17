resource "google_billing_budget" "this" {
  count           = var.enable_budget ? 1 : 0
  provider        = google-beta
  billing_account = var.billing_account
  display_name    = "caseproof-${local.project}"

  budget_filter {
    projects               = ["projects/${local.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.8
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  lifecycle {
    precondition {
      condition     = var.billing_account != ""
      error_message = "billing_account is required when enable_budget is true."
    }
  }
}
