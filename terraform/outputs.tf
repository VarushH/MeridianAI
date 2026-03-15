output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github_provider.name
  description = "The Workload Identity Provider ID to put in GitHub Secrets (WIF_PROVIDER)"
}

output "service_account_email" {
  value       = google_service_account.github_actions_sa.email
  description = "The Service Account email to put in GitHub Secrets (GCP_SA_EMAIL)"
}

output "artifact_registry_repo" {
  value       = var.manage_artifact_registry ? google_artifact_registry_repository.docker_repo[0].repository_id : var.repository_id
  description = "The Artifact Registry Repository Name"
}
