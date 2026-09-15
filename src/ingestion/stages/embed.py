"""Embed stage: text-embedding abstraction over Chroma's default embedder."""

from abc import ABC, abstractmethod

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class ChromaEmbedder(Embedder):
    def __init__(self) -> None:
        self._fn = DefaultEmbeddingFunction()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)
