"""Document ingestion: scan data/raw → load & chunk → embed → store in ChromaDB."""

import argparse
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pydantic import BaseModel

from src.config import settings


class Chunk(BaseModel):
    text: str
    source: str
    index: int

    @property
    def id(self) -> str:
        return f"{self.source}:{self.index}"


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class ChromaEmbedder(Embedder):
    """Default embedding function bundled with ChromaDB (ONNX MiniLM)."""

    def __init__(self) -> None:
        self._fn = DefaultEmbeddingFunction()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)


def scan_documents(raw_dir: Path = settings.raw_dir) -> list[Path]:
    return sorted(raw_dir.glob("**/*.md"))


def chunk_text(
    text: str,
    chunk_size: int = settings.chunk_size,
    overlap: int = settings.overlap,
) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
    if current:
        chunks.append(current)
    return chunks


def load_and_chunk(
    path: Path,
    chunk_size: int = settings.chunk_size,
    overlap: int = settings.overlap,
) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    return [
        Chunk(text=part, source=path.name, index=index)
        for index, part in enumerate(chunk_text(text, chunk_size, overlap))
    ]


def store(
    chunks: list[Chunk],
    embedder: Embedder,
    client: chromadb.Client,
    collection_name: str = settings.collection_name,
) -> int:
    collection = client.get_or_create_collection(name=collection_name)
    ids = [chunk.id for chunk in chunks]
    documents = [chunk.text for chunk in chunks]
    metadatas = [{"source": chunk.source, "index": chunk.index} for chunk in chunks]
    embeddings = embedder.embed_texts(documents)
    collection.upsert(
        ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
    )
    return len(chunks)


def run_pipeline(
    raw_dir: Path = settings.raw_dir,
    persist_dir: Path = settings.persist_dir,
    chunk_size: int = settings.chunk_size,
    overlap: int = settings.overlap,
    embedder: Embedder | None = None,
    recreate: bool = False,
) -> list[Chunk]:
    if recreate and persist_dir.exists():
        shutil.rmtree(persist_dir)

    chunks: list[Chunk] = []
    for path in scan_documents(raw_dir):
        chunks.extend(load_and_chunk(path, chunk_size, overlap))

    client = chromadb.PersistentClient(path=str(persist_dir))
    store(chunks, embedder or ChromaEmbedder(), client)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest data/raw into ChromaDB")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_dir)
    parser.add_argument("--persist-dir", type=Path, default=settings.persist_dir)
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--overlap", type=int, default=settings.overlap)
    parser.add_argument(
        "--recreate", action="store_true", help="wipe the collection before ingesting"
    )
    args = parser.parse_args()

    chunks = run_pipeline(
        raw_dir=args.raw_dir,
        persist_dir=args.persist_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        recreate=args.recreate,
    )
    print(
        f"Ingested {len(chunks)} chunk(s) from {args.raw_dir} into {args.persist_dir}"
    )


if __name__ == "__main__":
    main()
