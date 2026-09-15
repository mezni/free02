"""Embed stage: text-embedding abstraction over LlamaIndex's HuggingFace embed model."""

from abc import ABC, abstractmethod

from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return a list of vectors, one per input text."""


class ChromaEmbedder(Embedder):
    """Chroma-compatible embedder delegating to LlamaIndex ``Settings.embed_model``."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return Settings.embed_model.get_text_embedding_batch(texts)