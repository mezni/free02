"""Embedding (pgvector) repository."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.db.models import Chunk
from src.db.repositories.upsert import upsert


class EmbeddingRepository:
    """Store and similarity-search chunk embeddings with pgvector."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, chunk: Chunk) -> Chunk:
        self._session.add(chunk)
        return chunk

    def store_many(self, chunks: list[Chunk]) -> list[Chunk]:
        self._session.add_all(chunks)
        return chunks

    def upsert(self, chunk: Chunk) -> Chunk:
        upsert(self._session, Chunk, chunk, "chunk_id")
        return chunk

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        *,
        tenant_id: str | None = None,
        filters: list | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Return (chunk, cosine_distance) rows ordered by relevance.

        ``filters`` carries a full SQLAlchemy predicate list built by a strategy
        (e.g. ``FilterBundle.as_predicates``). When provided it is used as-is and
        the legacy ``tenant_id`` shorthand is ignored; callers wanting tenancy
        enforcement should include it in the predicate list.
        """
        if filters is None:
            filters = [Chunk.is_active.is_(True)]
            if tenant_id is not None:
                filters.append(Chunk.doc_metadata["tenant_id"].astext == tenant_id)

        distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
        stmt = (
            select(Chunk, distance)
            .where(*filters)
            .order_by(distance)
            .limit(top_k)
        )
        return [(chunk, float(score)) for chunk, score in self._session.execute(stmt)]

    def delete_by_doc_version(self, relative_path: str, version: int) -> int:
        stmt = (
            delete(Chunk)
            .where(Chunk.relative_path == relative_path, Chunk.version == version)
            .execution_options(synchronize_session=False)
        )
        result = self._session.execute(stmt)
        return result.rowcount or 0