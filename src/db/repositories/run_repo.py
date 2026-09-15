"""Pipeline run repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PipelineRun
from src.db.repositories.upsert import upsert


class RunRepository:
    """CRUD + finalization queries for pipeline run records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: PipelineRun) -> PipelineRun:
        self._session.add(run)
        return run

    def upsert(self, run: PipelineRun) -> PipelineRun:
        upsert(self._session, PipelineRun, run, "run_id")
        return run

    def get(self, run_id: str) -> PipelineRun | None:
        return self._session.get(PipelineRun, run_id)

    def list_recent(self, limit: int = 10) -> list[PipelineRun]:
        stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def list_by_status(self, status: str) -> list[PipelineRun]:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.status == status)
            .order_by(PipelineRun.started_at.desc())
        )
        return list(self._session.scalars(stmt))

    def finalize(
        self,
        run_id: str,
        *,
        status: str,
        completed_at: datetime,
        duration_seconds: float,
        chunks_created: int,
        files_new: int,
        files_modified: int,
        files_deleted: int,
        files_unchanged: int,
        error_message: str | None = None,
    ) -> PipelineRun | None:
        run = self.get(run_id)
        if run is None:
            return None
        run.status = status
        run.completed_at = completed_at
        run.duration_seconds = duration_seconds
        run.chunks_created = chunks_created
        run.files_new = files_new
        run.files_modified = files_modified
        run.files_deleted = files_deleted
        run.files_unchanged = files_unchanged
        run.error_message = error_message
        return run