"""Chunk repository."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.db.models import Chunk


class ChunkRepository:
    """CRUD + lifecycle queries for chunk rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, chunk: Chunk) -> Chunk:
        self._session.add(chunk)
        return chunk

    def add_all(self, chunks: list[Chunk]) -> list[Chunk]:
        self._session.add_all(chunks)
        return chunks

    def get(self, chunk_id: str) -> Chunk | None:
        stmt = select(Chunk).where(Chunk.chunk_id == chunk_id)
        return self._session.scalar(stmt)

    def list_by_doc(self, doc_id: str) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
        )
        return list(self._session.scalars(stmt))

    def count_active(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.is_active.is_(True))
        )
        return int(self._session.scalar(stmt) or 0)

    def deactivate_by_doc_version(self, relative_path: str, version: int) -> int:
        stmt = (
            update(Chunk)
            .where(
                Chunk.relative_path == relative_path,
                Chunk.version == version,
                Chunk.is_active.is_(True),
            )
            .values(is_active=False)
            .execution_options(synchronize_session=False)
        )
        result = self._session.execute(stmt)
        return result.rowcount or 0