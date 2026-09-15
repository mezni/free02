"""Chunk stage: split text into chunks using LlamaIndex node parsers.

- Markdown files: Document Structure-Based Chunking (MarkdownNodeParser)
- All other files: Fixed-Size Chunking (TokenTextSplitter, token-based)
"""

from enum import Enum

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, TokenTextSplitter

from src.domain.models.chunk import Chunk

_MD_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}


class ChunkingStrategy(str, Enum):
    """Chunking strategy selector."""

    STRUCTURE = "structure"
    FIXED = "fixed"


def chunking_strategy_for(file_extension: str) -> ChunkingStrategy:
    """Return STRUCTURE for markdown extensions, FIXED for everything else."""
    return (
        ChunkingStrategy.STRUCTURE
        if file_extension.lower() in _MD_EXTENSIONS
        else ChunkingStrategy.FIXED
    )


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
    *,
    strategy: ChunkingStrategy = ChunkingStrategy.FIXED,
) -> list[str]:
    """Chunk raw text using the specified LlamaIndex strategy.

    Raises ``ValueError`` if overlap exceeds chunk_size.
    """
    if overlap > chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than or equal to chunk_size ({chunk_size})"
        )

    doc = Document(text=text)

    if strategy is ChunkingStrategy.STRUCTURE:
        nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
    else:
        splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            include_metadata=False,
        )
        nodes = splitter.get_nodes_from_documents([doc])

    return [node.text for node in nodes]


def build_chunks(
    text: str,
    doc_id: str,
    run_id: str,
    chunk_size: int,
    overlap: int,
    *,
    strategy: ChunkingStrategy = ChunkingStrategy.FIXED,
) -> list[Chunk]:
    """Turn cleaned text into Chunk objects using the specified LlamaIndex strategy."""
    return [
        Chunk(content=part, run_id=run_id, doc_id=doc_id, index=index)
        for index, part in enumerate(
            chunk_text(text, chunk_size, overlap, strategy=strategy)
        )
    ]