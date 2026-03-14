import os
import tempfile

from google.cloud import aiplatform, storage
from langchain_google_vertexai import (
    VertexAIEmbeddings,
    ChatVertexAI,
    VectorSearchVectorStore,
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# ==========================================
# 1. Configuration & Initialization
# ==========================================
PROJECT_ID = "meridian-ai-platform"
REGION = "us-central1"
GCS_BUCKET_NAME = "meridian-ai-platform-vector-staging"
GCS_PREFIX = "uploads/"

# Initialize Vertex AI SDK
aiplatform.init(project=PROJECT_ID, location=REGION)

# Initialize the embedding model (Vertex AI Enterprise versions)
embeddings = VertexAIEmbeddings(model_name="text-embedding-004")

# Initialize the LLM (Gemini 1.5 Pro)
llm = ChatVertexAI(model_name="gemini-2.5-pro")

# ==========================================
# 2. Vector Database Setup
# ==========================================
vector_store = VectorSearchVectorStore.from_components(
    project_id=PROJECT_ID,
    region=REGION,
    embedding=embeddings,  # NOTE: singular "embedding", not "embeddings"
    index_id="projects/745639784437/locations/us-central1/indexes/340754046610571264",
    endpoint_id="projects/745639784437/locations/us-central1/indexEndpoints/289965405500342272",
    gcs_bucket_name=GCS_BUCKET_NAME,
    stream_update=True,
)

# ==========================================
# 3. Data Ingestion (Loading PDFs from GCS)
# ==========================================
def ingest_data_from_gcs():
    """Loads PDFs from a GCS bucket, extracts text, splits it, and stores it."""
    print(f"Connecting to GCS Bucket: {GCS_BUCKET_NAME}...")

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET_NAME)
    blobs = list(bucket.list_blobs(prefix=GCS_PREFIX))

    # Use a temp directory so files are not locked during processing
    tmp_dir = tempfile.mkdtemp()
    documents = []

    try:
        for blob in blobs:
            if blob.name.endswith(".pdf"):
                local_path = os.path.join(tmp_dir, os.path.basename(blob.name))
                blob.download_to_filename(local_path)
                loader = PyPDFLoader(local_path)
                docs = loader.load()
                print(docs)
                # Preserve the original GCS source in metadata
                for doc in docs:
                    doc.metadata["source"] = f"gs://{GCS_BUCKET_NAME}/{blob.name}"
                documents.extend(docs)
    finally:
        # Clean up temp files after all processing is done
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not documents:
        print("No documents found in the specified bucket/prefix.")
        return

    print(f"Successfully loaded {len(documents)} page(s) from GCS.")

    # Split text into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split documents into {len(chunks)} searchable chunks.")

    # Embed and store in Vertex AI Vector Search
    print("Embedding chunks and pushing to Vertex AI Vector Search...")
    vector_store.add_documents(chunks)
    print("Ingestion complete!")




# ==========================================
# 5. Execution
# ==========================================
if __name__ == "__main__":
    ingest_data_from_gcs()

    # Query the RAG system based on your PDF content
    # ask_question("Summarize the main points of the Q3 financial report.")


# ==========================================
# 4. Building the RAG Chain
# ==========================================
def ask_question(query: str):
    """Retrieves context and generates an answer using Gemini."""
    print(f"\nQuery: {query}")

    # Create a retriever from the vector store (fetch top 3 most relevant chunks)
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # Define the system prompt to guide the LLM's behavior
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

    # Chain 1: Formats the prompt with retrieved documents and passes to the LLM
    question_answer_chain = create_stuff_documents_chain(llm, prompt)

    # Chain 2: Orchestrates the retrieval step and the QA step
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    # Execute the chain
    response = rag_chain.invoke({"input": query})

    print("\n--- Answer ---")
    print(response["answer"])
    print("--------------")

# ==========================================
# 5. Execution
# ==========================================
if __name__ == "__main__":
    # 1. Ingest the data into the database
    # (You only need to run this once to populate your Vector Search collection)
    # ingest_data()

    # 2. Query the RAG system
    # ask_question("What all countries does acme manufacturing operates in?")
    # ask_question("How much percentage of the manufacturing workface will retire in next five years?")
    # ask_question("What is the COGS in FY2024")
    ask_question("What is the Revenue  in FY2022")