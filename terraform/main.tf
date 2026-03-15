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

resource "google_project_service" "iamcredentials_api" {
  service = "iamcredentials.googleapis.com"
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

# ---------------------------------------------------------------------------------------------------------------------
# Workload Identity Federation for GitHub Actions
# ---------------------------------------------------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-actions-pool-meridian"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions to deploy MeridianAI"
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC identity pool provider for Github Actions"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "attribute.repository_owner == \"${split(\"/\", var.github_repository)[0]}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Bind the service account to the WIF provider for the specific GitHub repo
resource "google_service_account_iam_member" "github_wif_sa_impersonation" {
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository_owner/${split(\"/\", var.github_repository)[0]}"
}
