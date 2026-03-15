# Stage 1: Build the Vite React Frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install dependencies
COPY frontend/package.json frontend/package-lock.json* frontend/bun.lock* ./
# Fallback to npm if bun/yarn not specified ideally
RUN npm install

# Build the frontend bundle
COPY frontend/ .
# VITE_API_URL is intentionally left empty so it defaults to relative paths (e.g., /api/...)
RUN npm run build


# Stage 2: Build the FastAPI Backend & Serve Frontend
FROM python:3.11-slim

WORKDIR /app

# Ensure we have CA certs and other basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ .

# Copy the built frontend static files from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the port Cloud Run expects (Cloud Run provides the PORT environment variable, usually 8080)
EXPOSE 8080

# Run Uvicorn. Use the PORT environment variable provided by Cloud Run, fallback to 8080.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
