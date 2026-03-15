"""
FastAPI Backend — Procurement Audit & RAG Document Intelligence
===============================================================
Exposes REST endpoints for:
  1. Running multi-agent procurement audits  (agent.py)
  2. Uploading documents into Vertex AI Vector Search  (rag.py)
  3. Querying the RAG pipeline
"""

import sys
import os
import shutil
import tempfile
import traceback
from datetime import datetime
from typing import Optional

# Ensure UTF-8 output on Windows terminals to avoid charmap errors
if sys.stdout.encoding.lower() != 'utf-8' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Import from the UNCHANGED user modules
# ---------------------------------------------------------------------------
from agent import ProcurementSupervisor
from rag import ingest_data_from_gcs, ask_question, vector_store, embeddings, llm as rag_llm

# LangChain / Pipeline Imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor

# ---------------------------------------------------------------------------
# Additional imports needed for the local-upload ingestion path
# ---------------------------------------------------------------------------
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# App Initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Procurement Intelligence API",
    version="1.0.0",
    description="Multi-agent procurement audit & RAG document intelligence backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supervisor = ProcurementSupervisor()

# In-memory upload tracker (reset on restart)
_upload_history: list[dict] = []
_server_start_time = datetime.utcnow()

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# System Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
def system_status():
    """Return real-time system configuration and health information."""
    from rag import (
        PROJECT_ID, REGION, GCS_BUCKET_NAME, GCS_PREFIX,
        vector_store, embeddings, llm,
    )
    import sys, platform

    uptime_seconds = int((datetime.utcnow() - _server_start_time).total_seconds())
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Try to pull index / endpoint IDs from the vector_store internals
    try:
        index_id = vector_store._searcher._index.resource_name
    except Exception:
        index_id = "projects/745639784437/locations/us-central1/indexes/340754046610571264"

    try:
        endpoint_id = vector_store._searcher._index_endpoint.resource_name
    except Exception:
        endpoint_id = "projects/745639784437/locations/us-central1/indexEndpoints/289965405500342272"

    return {
        "backend": {
            "status": "healthy",
            "uptime": f"{hours:02d}h {minutes:02d}m {seconds:02d}s",
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
        },
        "gcp": {
            "project_id": PROJECT_ID,
            "region": REGION,
        },
        "storage": {
            "gcs_bucket": GCS_BUCKET_NAME,
            "gcs_prefix": GCS_PREFIX,
        },
        "vector_search": {
            "index_id": index_id,
            "endpoint_id": endpoint_id,
            "stream_update": True,
        },
        "models": {
            "embedding": "text-embedding-004",
            "llm": "gemini-2.5-pro",
            "llm_framework": "Vertex AI / LangChain",
        },
        "ingestion": {
            "uploads_this_session": len(_upload_history),
        },
    }


# ============================================================
# AGENT  endpoints
# ============================================================

class AuditRequest(BaseModel):
    request_text: str

class AuditResponse(BaseModel):
    risk_result: str
    tax_result: str
    control_result: str
    cfo_memo: str

@app.post("/api/agent/audit", response_model=AuditResponse)
def run_audit(payload: AuditRequest):
    """Run the full multi-agent procurement audit and return all phase results."""
    try:
        result = supervisor.run_audit(payload.request_text)
        return AuditResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# RAG  endpoints
# ============================================================

class QueryRequest(BaseModel):
    query: str
    retriever_type: str = "similarity"

class QueryResponse(BaseModel):
    answer: str

@app.post("/api/rag/ask", response_model=QueryResponse)
def rag_query(payload: QueryRequest):
    """Query the RAG pipeline (Vertex AI Vector Search + Gemini)."""
    try:
        # Configure Base Retriever
        base_retriever = vector_store.as_retriever(search_kwargs={"k": 3})

        # Route Selection
        if payload.retriever_type == "contextual":
            # Using Contextual Compression as a high-quality retrieval strategy
            # This fetches k=10 and uses Gemini to 'refine' / 'compress' the documents
            compressor = LLMChainExtractor.from_llm(rag_llm)
            retriever = ContextualCompressionRetriever(
                base_compressor=compressor, 
                base_retriever=vector_store.as_retriever(search_kwargs={"k": 10})
            )
        elif payload.retriever_type == "multiquery":
            import logging
            logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)
            retriever = MultiQueryRetriever.from_llm(retriever=base_retriever, llm=rag_llm)
        else:
            retriever = base_retriever

        # Note: 'mmr' requested but falling back to similarity if backend lacks implementation
        # The UI still shows MMR, but it will use similarity search for stability.

        system_prompt = (
            "You are a helpful assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer based on the context, say that you don't know. "
            "Keep the answer concise and accurate."
            "\n\n"
            "Context: {context}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        question_answer_chain = create_stuff_documents_chain(rag_llm, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        response = rag_chain.invoke({"input": payload.query})

        return QueryResponse(answer=response["answer"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DOCUMENT UPLOAD  endpoint  (local PDF → Vector Search)
# ============================================================

@app.post("/api/rag/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """
    Accept one or more PDF uploads, chunk them, embed with Vertex AI,
    and push into the existing Vector Search index.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    results = []
    tmp_dir = tempfile.mkdtemp()

    try:
        for upload in files:
            if not upload.filename.lower().endswith(".pdf"):
                results.append({
                    "filename": upload.filename,
                    "status": "skipped",
                    "reason": "Only PDF files are supported.",
                })
                continue

            # Save to temp location (must use await to read async UploadFile correctly)
            local_path = os.path.join(tmp_dir, upload.filename)
            contents = await upload.read()
            with open(local_path, "wb") as f:
                f.write(contents)

            # Upload original PDF to GCS under uploads/ so it's persisted in the bucket
            try:
                from google.cloud import storage as gcs
                from rag import PROJECT_ID, GCS_BUCKET_NAME, GCS_PREFIX
                gcs_client = gcs.Client(project=PROJECT_ID)
                bucket = gcs_client.bucket(GCS_BUCKET_NAME)
                gcs_path = f"{GCS_PREFIX}{upload.filename}"
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_path, content_type="application/pdf")
                print(f"[Upload] '{upload.filename}': Saved to gs://{GCS_BUCKET_NAME}/{gcs_path}")
            except Exception as gcs_err:
                print(f"[Upload] WARNING: Could not save to GCS: {gcs_err}")

            # Load & split
            loader = PyPDFLoader(local_path)
            docs = loader.load()
            print(f"[Upload] '{upload.filename}': {len(docs)} page(s) loaded.")

            for doc in docs:
                doc.metadata["source"] = f"upload://{upload.filename}"

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
            )
            chunks = text_splitter.split_documents(docs)
            print(f"[Upload] '{upload.filename}': {len(chunks)} chunk(s) created.")

            if not chunks:
                print(f"[Upload] '{upload.filename}': No chunks — skipping indexing.")
                results.append({
                    "filename": upload.filename,
                    "status": "skipped",
                    "reason": "No extractable text found in PDF (may be a scanned/image-based PDF).",
                })
                continue

            # Embed & store
            print(f"[Upload] '{upload.filename}': Ingesting {len(chunks)} chunk(s) into Vector Search…")
            vector_store.add_documents(chunks)
            print(f"[Upload] '{upload.filename}': Successfully ingested {len(chunks)} chunk(s).")

            results.append({
                "filename": upload.filename,
                "status": "ingested",
                "pages": len(docs),
                "chunks": len(chunks),
            })
    except Exception as e:
        tb = traceback.format_exc()
        print(f"UPLOAD ERROR:\n{tb}")  # prints to server console
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _upload_history.extend(results)
    return {"results": results}


@app.get("/api/rag/uploads")
def list_uploads():
    """Return the history of uploaded documents (in-memory, resets on restart)."""
    return {"uploads": _upload_history}


@app.post("/api/rag/ingest-gcs")
def trigger_gcs_ingestion():
    """Trigger the original GCS-based ingestion from rag.py."""
    try:
        ingest_data_from_gcs()
        return {"status": "GCS ingestion complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# FRONTEND STATIC SERVING (CATCH-ALL)
# ============================================================
# This must come AFTER all API routes to avoid shadowing them.

# Check if the frontend dist exists (we are running in the unified container)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(frontend_dir):
    print(f"Serving frontend from {frontend_dir}")
    # Mount assets folder explicitly if it exists
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
    # Catch-all route to serve the SPA index.html for unknown paths
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # Prevent shadowing API routes completely
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
            
        # Try to serve requested file if it exists (e.g., favicon.ico, images)
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Otherwise, fall back to React's index.html
        return FileResponse(os.path.join(frontend_dir, "index.html"))
