"""M3: embedding client — OpenAI text-embedding-3-small behind a Protocol.

The Protocol exists so tests and the eval harness can swap in a deterministic
fake without network access; production code should depend on `Embedder`, not
on the OpenAI class directly.
"""

import os
from typing import Protocol

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

log = structlog.get_logger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMS = 1536  # must match doc_chunks.embedding VECTOR(1536)
BATCH_SIZE = 100


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, model: str = EMBEDDING_MODEL):
        from openai import OpenAI

        self._client = OpenAI()  # reads OPENAI_API_KEY from the environment
        self._model = model

    @retry(stop=stop_after_attempt(4), wait=wait_exponential_jitter(initial=1, max=20), reraise=True)
    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=batch)
        return [item.embedding for item in response.data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            vectors.extend(self._embed_batch(batch))
            log.debug("embedded_batch", n=len(batch), total=len(vectors))
        return vectors
