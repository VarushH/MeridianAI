<p align="center">
  <h1 align="center">MeridianAI</h1>
  <p align="center">
    <strong>Multi-Agent Procurement Audit & RAG Document Intelligence Platform</strong>
  </p>
  <p align="center">
    Built with FastAPI · React · LangGraph · Gemini · Vertex AI · Cloud Run
  </p>
</p>

---

## Architecture

<p align="center">
  <img src="Supporting Documents/architecture_diagram.png" alt="MeridianAI Architecture" width="100%"/>
</p>

| Layer | Components | Technologies |
|---|---|---|
| **Client** | React Frontend | Vite, TypeScript, Tailwind CSS, Shadcn UI |
| **Compute** | FastAPI Backend on GCP Cloud Run | Uvicorn, CORS, Static File Serving |
| **AI Agents** | Procurement Audit Agent, RAG Pipeline | LangGraph, LangChain, Gemini 2.5 Pro |
| **Data & AI** | Gemini LLMs, Vertex AI Vector Search, Cloud Storage | Embeddings, ANN Endpoint, GCS Buckets |
| **Security** | Secret Manager | Runtime API Key Injection |
| **CI/CD** | GitHub Actions → Cloud Build → Artifact Registry → Cloud Run | Automated Provisioning & Deployment |

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Local Development](#local-development)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
- [Running with Docker](#running-with-docker)
- [Environment Variables](#environment-variables)
- [Deploying to GCP (From Scratch)](#deploying-to-a-brand-new-gcp-project-from-scratch)
  - [Step 1: Create Project & Enable Billing](#step-1-create-the-project-and-enable-billing)
  - [Step 2: Create a Service Account](#step-2-create-a-powerful-service-account)
  - [Step 3: Configure GitHub Secrets](#step-3-configure-github-secrets)
  - [Step 4: Trigger the Pipeline](#step-4-trigger-the-pipeline)

---

## Prerequisites

- **Python** 3.11+
- **Node.js** 20+
- **Google Cloud SDK** (`gcloud` CLI) — [Install Guide](https://cloud.google.com/sdk/docs/install)
- **Docker** (optional, for containerised local runs)
- A **GCP project** with billing enabled
- A **Google API Key** for Gemini access

---

## Project Structure

```
MeridianAI/
├── backend/
│   ├── api/            # FastAPI app, endpoints, and middleware
│   ├── agent/          # LangGraph multi-agent procurement audit logic
│   ├── rag/            # RAG pipeline — document indexing & QA
│   ├── config/         # Pydantic settings and app configuration
│   └── logger/         # Structured logging with GCS flush support
├── frontend/
│   ├── src/
│   │   ├── components/ # Shadcn UI and custom React components
│   │   ├── pages/      # Application pages (RAG Q&A, Procurement Audit)
│   │   └── hooks/      # Custom React hooks
│   └── package.json
├── .github/
│   └── workflows/
│       └── deploy.yml  # CI/CD — full GCP provisioning & Cloud Run deploy
├── credentials/        # Local service account keys (git-ignored)
├── Dockerfile          # Multi-stage build (Node + Python)
├── docker-compose.yml  # Local containerised development
├── requirements.txt    # Python dependencies
└── .env                # Local environment variables (git-ignored)
```

---

## Local Development

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/<your-org>/MeridianAI.git
cd MeridianAI

# Create and activate a virtual environment
python -m venv .meridian
# Windows
.meridian\Scripts\activate
# macOS / Linux
source .meridian/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Set GCP credentials for local development
# Windows (cmd)
set GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json
# Windows (PowerShell)
$env:GOOGLE_APPLICATION_CREDENTIALS="./credentials/service-account.json"
# macOS / Linux
export GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

# (Optional) Set your quota project
gcloud auth application-default set-quota-project <your-gcp-project-id>

# Start the backend dev server
uvicorn api.main:app --app-dir backend --reload --port 8080
```

The API will be available at **http://localhost:8080**. Interactive docs at **http://localhost:8080/docs**.

### 2. Frontend Setup

```bash
# In a new terminal, navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite dev server
npm run dev
```

The frontend will be available at **http://localhost:5173** (default Vite port) and will proxy API calls to the backend.

---

## Running with Docker

Build and run the unified container that serves both the frontend and backend:

```bash
# Build the image
docker build -t meridian-ai .

# Run the container
docker run -p 8080:8080 --env-file .env meridian-ai
```

Or use Docker Compose:

```bash
docker compose up --build
```

The application will be accessible at **http://localhost:8080**.

---

## Environment Variables

Create a `.env` file in the project root. See the table below for required and optional variables:

| Variable | Required | Description |
|---|:---:|---|
| `ENVIRONMENT` | ✅ | `local` or `production` |
| `GCP_PROJECT_ID` | ✅ | Your Google Cloud project ID |
| `GCP_REGION` | ✅ | GCP region (e.g., `us-central1`) |
| `GOOGLE_API_KEY` | ✅ | Gemini API key |
| `GCS_BUCKET_NAME` | ✅ | GCS bucket for vector staging & uploads |
| `GCS_PREFIX` | | Upload path prefix (default: `uploads/`) |
| `GCP_SERVICE_ACCOUNT_PATH` | | Path to local service account JSON |
| `VERTEX_LLM_MODEL_NAME` | | LLM model (default: `gemini-2.5-pro`) |
| `VERTEX_EMBEDDING_MODEL_NAME` | | Embedding model (default: `gemini-embedding-2-preview`) |
| `VECTOR_SEARCH_INDEX_ID` | ✅ | Vertex AI Vector Search index resource ID |
| `VECTOR_SEARCH_INDEX_ENDPOINT_ID` | ✅ | Vertex AI Vector Search endpoint resource ID |

---

## Deploying to a Brand New GCP Project (From Scratch)

> If you are moving this codebase to an entirely new GCP project where **nothing** has been configured, follow these exact manual steps **once**. After this initial setup, the GitHub Action will fully manage the project for you.

### Step 1: Create the Project and Enable Billing

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a **new project** (e.g., `meridian-ai-prod`).
3. Link an **active Billing Account** to the project.

> [!IMPORTANT]
> Cloud Run and Vertex AI **require active billing** to function. The deployment pipeline will fail silently without it.

### Step 2: Create a Powerful Service Account

The GitHub Action acts as a **"robot administrator"**. It needs permission to enable APIs, create storage buckets, provision vector indexes, and deploy services.

Open Google Cloud Shell (or your local terminal authenticated to your account) and run:

```bash
# Set your active project
export PROJECT_ID="meridian-ai-prod"
gcloud config set project $PROJECT_ID

# Create the GitHub Deployer service account
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=$PROJECT_ID

# Grant the "Editor" role so it can build infrastructure
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/editor"

# Grant IAM Admin role so it can manage service-level permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/resourcemanager.projectIamAdmin"

# Generate the JSON key file
gcloud iam service-accounts keys create github-deployer-key.json \
  --iam-account=github-deployer@${PROJECT_ID}.iam.gserviceaccount.com
```

> [!CAUTION]
> The `github-deployer-key.json` file contains highly privileged credentials.
> **Never commit this file to version control.** Store it securely and delete the local copy after adding it to GitHub Secrets.

### Step 3: Configure GitHub Secrets

Navigate to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add the following three secrets:

| Secret Name | Value |
|---|---|
| `GCP_PROJECT_ID` | Your new project ID (e.g., `meridian-ai-prod`) |
| `GCP_CREDENTIALS_JSON` | The **entire contents** of `github-deployer-key.json` |
| `GOOGLE_API_KEY` | Your Gemini API key |

### Step 4: Trigger the Pipeline

Push your code to the `main` branch (or manually trigger the workflow via the **Actions** tab).

```bash
git push origin main
```

The GitHub Action (`.github/workflows/deploy.yml`) will now automatically:

1. ✅ **Enable** all necessary GCP APIs natively.
2. ✅ **Provision** the Cloud Storage buckets.
3. ✅ **Create** the Vertex AI Vector Search Index & Endpoint *(expect ~30+ min on first run)*.
4. ✅ **Inject** your `GOOGLE_API_KEY` into GCP Secret Manager.
5. ✅ **Build** the Docker image and push to Artifact Registry.
6. ✅ **Deploy** the Cloud Run service with public access.

> [!NOTE]
> The very first deployment can take **30–45 minutes** due to Vector Search index creation. Subsequent deployments typically complete in **3–5 minutes**.

Once complete, the Action logs will print your live Cloud Run URL. **Your application is now fully automated and live!** 🚀

---

## License

This project is proprietary. All rights reserved.