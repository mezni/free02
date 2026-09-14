"""Data ingestion: loads markdown documents from data/raw into an in-memory index."""

from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DOCUMENTS: list[dict[str, str]] = []


def ingest_dir(directory: Path = RAW_DIR) -> int:
    """Load every *.md file from `directory` into the in-memory index.

    Returns the number of documents ingested.
    """
    global DOCUMENTS
    DOCUMENTS = []
    for path in sorted(directory.glob("*.md")):
        DOCUMENTS.append(
            {
                "name": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return len(DOCUMENTS)