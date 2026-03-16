output "service_account_email" {
  value       = google_service_account.github_actions_sa.email
  description = "The Service Account email to generate the JSON key for."
}

output "artifact_registry_repo" {
  value       = var.manage_artifact_registry ? google_artifact_registry_repository.docker_repo[0].repository_id : var.repository_id
  description = "The Artifact Registry Repository Name"
}
