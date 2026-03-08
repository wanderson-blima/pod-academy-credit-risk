# Monitoring Module — Phase 6.1
# Creates notification topic and operational alarms for the OCI Data Lakehouse
#
# Alarms:
#   1. Data Flow run failures
#   2. Object Storage growth threshold
#   3. Budget critical (> 80% consumed)

# ─── Notification Topic ──────────────────────────────────────────────────

resource "oci_ons_notification_topic" "ops_alerts" {
  compartment_id = var.compartment_ocid
  name           = "${var.project_prefix}-ops-alerts"
  description    = "Operational alerts for ${var.project_prefix} data platform"
}

resource "oci_ons_subscription" "email_alert" {
  compartment_id = var.compartment_ocid
  topic_id       = oci_ons_notification_topic.ops_alerts.id
  protocol       = "EMAIL"
  endpoint       = var.alert_email
}

# ─── Alarm: Data Flow Failures ───────────────────────────────────────────

resource "oci_monitoring_alarm" "dataflow_failures" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-dataflow-failures"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "oci_dataflow"
  query                 = "RunsFailed[1h].sum() > 0"
  severity              = "CRITICAL"
  body                  = "Data Flow run failed in ${var.project_prefix} pipeline. Check OCI Console > Data Flow > Runs for details."
  pending_duration      = "PT5M"
  repeat_notification_duration = "PT1H"

  destinations = [oci_ons_notification_topic.ops_alerts.id]
}

# ─── Alarm: Object Storage Growth ────────────────────────────────────────

resource "oci_monitoring_alarm" "storage_growth" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-storage-growth"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "oci_objectstorage"
  query                 = "StoredBytes[1d].max() > 53687091200"
  severity              = "WARNING"
  body                  = "Object Storage usage exceeded 50 GB in ${var.project_prefix}. Review data retention policies."
  pending_duration      = "PT1H"
  repeat_notification_duration = "PT24H"

  destinations = [oci_ons_notification_topic.ops_alerts.id]
}

# ─── Alarm: Budget Critical ─────────────────────────────────────────────

resource "oci_monitoring_alarm" "budget_critical" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-budget-critical"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "oci_budget"
  query                 = "BudgetActualSpend[1d].max() / BudgetAmount[1d].max() > 0.8"
  severity              = "CRITICAL"
  body                  = "Budget consumption exceeded 80% in ${var.project_prefix}. Consider stopping non-essential resources."
  pending_duration      = "PT1H"
  repeat_notification_duration = "PT4H"

  destinations = [oci_ons_notification_topic.ops_alerts.id]
}

# ═══════════════════════════════════════════════════════════════════════════
# ML Model Monitoring — Custom Metrics Alarms
# Namespace: credit_risk_model (published by oci/model/oci_metrics.py)
# ═══════════════════════════════════════════════════════════════════════════

# ─── ML Notification Topic (separate from ops) ─────────────────────────

resource "oci_ons_notification_topic" "ml_alerts" {
  compartment_id = var.compartment_ocid
  name           = "${var.project_prefix}-ml-alerts"
  description    = "ML model monitoring alerts for ${var.project_prefix}"
}

resource "oci_ons_subscription" "ml_email_alert" {
  compartment_id = var.compartment_ocid
  topic_id       = oci_ons_notification_topic.ml_alerts.id
  protocol       = "EMAIL"
  endpoint       = var.alert_email
}

# ─── Alarm: Score PSI Critical (drift detected) ───────────────────────

resource "oci_monitoring_alarm" "ml_psi_critical" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-ml-psi-critical"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "credit_risk_model"
  query                 = "credit_risk.score_psi[1d].max() >= 0.25"
  severity              = "CRITICAL"
  body                  = "Model score PSI >= 0.25 in ${var.project_prefix}. Score distribution has shifted — retraining required. Check OCI Console > Monitoring > credit_risk_model."
  pending_duration      = "PT5M"
  repeat_notification_duration = "PT4H"

  destinations = [oci_ons_notification_topic.ml_alerts.id]
}

# ─── Alarm: KS Degradation (model losing power) ──────────────────────

resource "oci_monitoring_alarm" "ml_ks_degraded" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-ml-ks-degraded"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "credit_risk_model"
  query                 = "credit_risk.ks_statistic[1d].min() < 0.20"
  severity              = "WARNING"
  body                  = "Model KS < 0.20 in ${var.project_prefix}. Discriminatory power degraded. Review model and consider retraining."
  pending_duration      = "PT1H"
  repeat_notification_duration = "PT24H"

  destinations = [oci_ons_notification_topic.ml_alerts.id]
}

# ─── Alarm: Feature Drift (input data changed) ───────────────────────

resource "oci_monitoring_alarm" "ml_feature_drift" {
  compartment_id        = var.compartment_ocid
  display_name          = "${var.project_prefix}-ml-feature-drift"
  is_enabled            = true
  metric_compartment_id = var.compartment_ocid
  namespace             = "credit_risk_model"
  query                 = "credit_risk.feature_psi[1d].max() >= 0.25"
  severity              = "CRITICAL"
  body                  = "Feature drift detected in ${var.project_prefix}. One or more features have PSI >= 0.25. Run: python monitor_model.py --publish-metrics"
  pending_duration      = "PT5M"
  repeat_notification_duration = "PT4H"

  destinations = [oci_ons_notification_topic.ml_alerts.id]
}
