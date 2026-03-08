output "topic_id" {
  description = "OCID of the notification topic"
  value       = oci_ons_notification_topic.ops_alerts.id
}

output "dataflow_alarm_id" {
  description = "OCID of the Data Flow failures alarm"
  value       = oci_monitoring_alarm.dataflow_failures.id
}

output "storage_alarm_id" {
  description = "OCID of the storage growth alarm"
  value       = oci_monitoring_alarm.storage_growth.id
}

output "budget_alarm_id" {
  description = "OCID of the budget critical alarm"
  value       = oci_monitoring_alarm.budget_critical.id
}
