from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.settings import settings


class BatchedGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
    """Wrapper that forces small-batch embedding to avoid API mismatch errors.

    The Google Generative AI API can return fewer embeddings than input texts
    when a large batch is sent in a single call.  This subclass overrides
    `embed_documents` to process texts in safe-sized batches automatically.
    """

    _BATCH_SIZE: int = 20  # safe ceiling; API limit is 100

    def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            all_embeddings.extend(super().embed_documents(batch, **kwargs))
        return all_embeddings


def get_embeddings():
    return BatchedGoogleEmbeddings(
        model=settings.embedding_model_name,
        google_api_key=settings.GOOGLE_API_KEY,
        task_type="retrieval_document",
        output_dimensionality=768,
    )
