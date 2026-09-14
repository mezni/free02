"""REST API layer."""

from fastapi import APIRouter

from src.ingestion import DOCUMENTS, ingest_dir

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/documents")
def list_documents() -> list[dict[str, str]]:
    return [{"name": doc["name"]} for doc in DOCUMENTS]


@router.post("/ingest")
def ingest() -> dict[str, int]:
    count = ingest_dir()
    return {"ingested": count}