variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud region to deploy to (e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "The exact GitHub repository name (e.g. your-org/MeridianAI)"
  type        = string
}

variable "repository_id" {
  description = "The name for the Artifact Registry Docker repository"
  type        = string
  default     = "meridianai-repo"
}

variable "manage_artifact_registry" {
  description = "Set to true to create the artifact registry"
  type        = bool
  default     = true
}
