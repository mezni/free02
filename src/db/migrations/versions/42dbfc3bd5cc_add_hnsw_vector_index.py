"""add hnsw vector index

Revision ID: 42dbfc3bd5cc
Revises: 35fbae838545
Create Date: 2026-09-15 11:52:42.026170

"""
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "42dbfc3bd5cc"
down_revision: str | None = "35fbae838545"
branch_labels: str | None = None
depends_on: str | None = None

INDEX_NAME = "ix_chunks_embedding_hnsw"


def upgrade() -> None:
    """Enable fast approximate-nearest-neighbour search on chunk embeddings."""
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Revert the migration."""
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")