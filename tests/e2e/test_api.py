"""End-to-end tests against the FastAPI application."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import api

app = FastAPI()
app.include_router(api.router)
client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documents_lists_sources():
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == ["SOP-FIN-004.md"]


def test_ingest_pipeline_is_incremental_and_idempotent(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text("hello world", encoding="utf-8")

    base = api.PipelineConfig()
    monkeypatch.setattr(
        api,
        "PipelineConfig",
        lambda: base.model_copy(
            update={"raw_dir": raw, "persist_dir": tmp_path / "chroma"}
        ),
    )

    first = client.post("/ingest")
    second = client.post("/ingest")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["ingested"] >= 1
    assert second.json()["ingested"] == 0
