# Cost Module — Outputs

output "budget_id" {
  description = "OCID of the budget"
  value       = oci_budget_budget.hackathon.id
}

output "alert_rule_ids" {
  description = "OCIDs of the budget alert rules"
  value = {
    warning_50  = oci_budget_alert_rule.warning_50.id
    critical_80 = oci_budget_alert_rule.critical_80.id
    forecast_100 = oci_budget_alert_rule.forecast_100.id
  }
}
