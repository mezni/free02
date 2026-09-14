"""Application entry point."""

import uvicorn
from fastapi import FastAPI

from src.api import router
from src.ingestion import ingest_dir

app = FastAPI(title="rag-project")
app.include_router(router)


def main() -> None:
    ingest_dir()
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()