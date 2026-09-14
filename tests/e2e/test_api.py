"""End-to-end tests against the FastAPI application."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documents_lists_sources():
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == ["SOP-FIN-004.md"]


def test_ingest_pipeline_end_to_end():
    response = client.post("/ingest")

    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] >= 1
