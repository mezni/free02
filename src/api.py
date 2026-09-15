"""REST API layer."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from src.core.logging import setup_logging
from src.ingestion import PipelineConfig, run_pipeline, scan_documents

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


class IngestResponse(BaseModel):
    ingested: int


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/documents")
def list_documents() -> list[str]:
    return [path.name for path in scan_documents()]


@router.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    _, chunks = run_pipeline(PipelineConfig())
    return IngestResponse(ingested=len(chunks))


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="rag-project", lifespan=lifespan)
    app.include_router(router)
    return app
