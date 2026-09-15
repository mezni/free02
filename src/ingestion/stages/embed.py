"""Embed stage: text-embedding abstraction over Chroma's default embedder."""

from abc import ABC, abstractmethod

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return a list of vectors, one per input text."""


class ChromaEmbedder(Embedder):
    _default_fn: DefaultEmbeddingFunction | None = None

    def __init__(self) -> None:
        if ChromaEmbedder._default_fn is None:
            ChromaEmbedder._default_fn = DefaultEmbeddingFunction()
        self._fn = ChromaEmbedder._default_fn

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)
