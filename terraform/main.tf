terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------------------------------------------------
# Apis
# ---------------------------------------------------------------------------------------------------------------------

resource "google_project_service" "cloudrun_api" {
  service = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry_api" {
  service = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------------------------------------------------
# Artifact Registry Repository
# ---------------------------------------------------------------------------------------------------------------------

resource "google_artifact_registry_repository" "docker_repo" {
  count         = var.manage_artifact_registry ? 1 : 0
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker repository for MeridianAI Cloud Run deployment"
  format        = "DOCKER"

  depends_on = [google_project_service.artifactregistry_api]
}

# ---------------------------------------------------------------------------------------------------------------------
# GitHub Actions Service Account
# ---------------------------------------------------------------------------------------------------------------------

resource "google_service_account" "github_actions_sa" {
  account_id   = "github-actions-meridian"
  display_name = "GitHub Actions Service Account for MeridianAI"
  description  = "Used by GitHub Actions to deploy to Cloud Run."
}

resource "google_project_iam_member" "sa_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

resource "google_project_iam_member" "sa_cloudrun_deployer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

resource "google_project_iam_member" "sa_iam_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}
