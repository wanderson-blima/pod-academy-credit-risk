# Data Science Module — Outputs

output "project_id" {
  description = "OCID of the Data Science project"
  value       = oci_datascience_project.ml.id
}

output "notebook_session_id" {
  description = "OCID of the notebook session"
  value       = var.create_notebook ? oci_datascience_notebook_session.training[0].id : ""
}

output "notebook_session_url" {
  description = "URL of the notebook session"
  value       = var.create_notebook ? oci_datascience_notebook_session.training[0].notebook_session_url : ""
}

output "batch_scoring_job_id" {
  description = "OCID of the batch scoring Data Science job"
  value       = oci_datascience_job.batch_scoring.id
}
