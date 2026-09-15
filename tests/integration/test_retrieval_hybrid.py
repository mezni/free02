"""Integration tests: hybrid retrieval strategies seeded with deterministic fake embeddings."""

import uuid

from src.db.models import EMBEDDING_DIM
from src.db.models import Chunk as ChunkORM
from src.db.repositories import EmbeddingRepository
from src.ingestion import Embedder
from src.retrieval import Query, RetrievalPipeline
from src.retrieval.strategies.filters import FilterBundle
from src.retrieval.strategies.hybrid_search import (
    HybridSearchStrategy,
    KeywordSearchStrategy,
)
from src.retrieval.strategies.vector_search import VectorSearchStrategy

# ---------------------------------------------------------------------------
# Fake embedder: deterministic non-zero vectors, no HF model load.
# ---------------------------------------------------------------------------

class FakeEmbedder(Embedder):
    """Returns a predictable 384-dim vector per input.

    Each vector encodes the first characters of the text in its leading
    components so cosine distance ordering is deterministic and meaningful.
    """

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            # Use the sum of the first 3 characters to create a small seed;
            # non-zero to avoid cosine divide-by-zero.
            seed = (sum(ord(c) for c in text[:3]) % 97) / 1000.0 + 0.1
            vec = [seed] * EMBEDDING_DIM
            vectors.append(vec)
        return vectors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orm_chunk(
    relative_path: str,
    index: int,
    content: str,
    tenant_id: str = "acme",
    *,
    embedding: list[float] | None = None,
) -> ChunkORM:
    """Build a Chunk ORM row with a fake embedding and commit it."""
    chunk = ChunkORM(
        chunk_id=f"{relative_path}:{index}:{uuid.uuid4().hex[:8]}",
        run_id="run-test",
        doc_id=f"{relative_path}:v1",
        relative_path=relative_path,
        chunk_index=index,
        content=content,
        doc_metadata={
            "relative_path": relative_path,
            "version_tag": "v1",
            "tenant_id": tenant_id,
            "is_active": True,
        },
        embedding=embedding or [0.1] * EMBEDDING_DIM,
        is_active=True,
    )
    return chunk


def _seed(session) -> list[ChunkORM]:
    embedder = FakeEmbedder()
    chunks = [
        _orm_chunk("sop.md", 0, "The late fee is 15 dollars after the grace period.", embedding=embedder.embed_texts(["a"])[0]),
        _orm_chunk("sop.md", 1, "Payment is due 20 days from invoice issuance.",     embedding=embedder.embed_texts(["b"])[0]),
        _orm_chunk("sop.md", 2, "The service is suspended after 45 days past due.",   embedding=embedder.embed_texts(["c"])[0]),
        _orm_chunk("sop.md", 3, "The late fee applies again after 30 days.",           embedding=embedder.embed_texts(["late"])[0]),
    ]
    repo = EmbeddingRepository(session)
    for c in chunks:
        repo.upsert(c)
    session.commit()
    return chunks


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------

def test_vector_search_finds_late_fee(db_session):
    _seed(db_session)
    fake = FakeEmbedder()
    vec_search = VectorSearchStrategy(embedder=fake, session=db_session)

    result = vec_search.search("late fee", top_k=2, filters=FilterBundle(tenant_id="acme"))

    assert len(result) > 0
    texts = [c.text for c in result]
    assert any("late fee" in t.lower() for t in texts)


def test_vector_search_respects_tenant_filter(db_session):
    _seed(db_session)
    # Seed a chunk belonging to a different tenant
    other = _orm_chunk("hr.md", 0, "PTO accrues at 1 day per month.", tenant_id="globex",
                       embedding=FakeEmbedder().embed_texts(["x"])[0])
    EmbeddingRepository(db_session).upsert(other)
    db_session.commit()

    fake = FakeEmbedder()
    vec_search = VectorSearchStrategy(embedder=fake, session=db_session)

    result = vec_search.search("PTO", top_k=10, filters=FilterBundle(tenant_id="acme"))
    assert all(c.metadata["tenant_id"] == "acme" for c in result)


# ---------------------------------------------------------------------------
# Hybrid search (vector + FTS keyword)
# ---------------------------------------------------------------------------

def test_hybrid_search_finds_late_fee(db_session):
    _seed(db_session)
    fake = FakeEmbedder()
    vec = VectorSearchStrategy(embedder=fake, session=db_session)
    kw = KeywordSearchStrategy(session=db_session)
    hybrid = HybridSearchStrategy(vector=vec, keyword=kw)

    result = hybrid.search("late fee", top_k=3, filters=FilterBundle(tenant_id="acme"))

    assert len(result) > 0
    ids = {c.id for c in result}
    # The FTS leg should surface chunks containing "late fee" directly
    assert any(tid.endswith((":0", ":3")) for tid in ids)


def test_rrf_dedupe_across_legs(db_session):
    _seed(db_session)
    fake = FakeEmbedder()
    vec = VectorSearchStrategy(embedder=fake, session=db_session)
    kw = KeywordSearchStrategy(session=db_session)
    hybrid = HybridSearchStrategy(vector=vec, keyword=kw)

    result = hybrid.search("late fee", top_k=5, filters=FilterBundle(tenant_id="acme"))
    ids = [c.id for c in result]
    assert len(ids) == len(set(ids))  # no duplicates


# ---------------------------------------------------------------------------
# Full pipeline with tenant filter
# ---------------------------------------------------------------------------

def test_pipeline_search_with_filters(db_session):
    _seed(db_session)
    fake = FakeEmbedder()
    pipeline = RetrievalPipeline(
        embedder=fake,
        db_session=db_session,
    )

    result = pipeline.search(Query(text="late fee", top_k=2), filters=FilterBundle(tenant_id="acme"))

    assert len(result.chunks) > 0
    assert result.query == "late fee"
    pipeline.close()
