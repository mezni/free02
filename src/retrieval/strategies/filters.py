"""Metadata filtering rules: scope search to tenants, roles, categories, and dates."""

from pydantic import BaseModel, Field
from sqlalchemy import Float, or_

from src.db.models import Chunk
from src.retrieval.models import Query


class FilterBundle(BaseModel):
    """Search-restriction rules applied before or during query execution."""

    tenant_id: str | None = None
    access_roles: list[str] = Field(default_factory=list)
    classification: str | None = None
    department: str | None = None
    category: str | None = None
    relative_paths: list[str] = Field(default_factory=list)
    modified_from: float | None = None
    modified_to: float | None = None
    is_active: bool = True

    def as_predicates(self) -> list:
        """Build the SQLAlchemy where-clause predicates for this bundle."""
        predicates: list = [Chunk.is_active.is_(self.is_active)]
        if self.tenant_id is not None:
            predicates.append(Chunk.doc_metadata["tenant_id"].astext == self.tenant_id)
        if self.classification:
            predicates.append(
                Chunk.doc_metadata["classification"].astext == self.classification
            )
        if self.department:
            predicates.append(Chunk.doc_metadata["department"].astext == self.department)
        if self.category:
            predicates.append(Chunk.doc_metadata["category"].astext == self.category)
        if self.access_roles:
            predicates.append(
                or_(
                    *(
                        Chunk.doc_metadata["access_roles"].astext.contains(role)
                        for role in self.access_roles
                    )
                )
            )
        if self.relative_paths:
            predicates.append(Chunk.relative_path.in_(self.relative_paths))
        if self.modified_from is not None:
            predicates.append(
                Chunk.doc_metadata["modified_at"].astext.cast(Float) >= self.modified_from
            )
        if self.modified_to is not None:
            predicates.append(
                Chunk.doc_metadata["modified_at"].astext.cast(Float) <= self.modified_to
            )
        return predicates


def build_filters(query: Query, **overrides) -> FilterBundle:
    """Derive a filter bundle from a user query.

    Applies tenant isolation whenever ``Query.tenant_id`` is supplied.
    """
    return FilterBundle(tenant_id=query.tenant_id, **overrides)


__all__ = ["FilterBundle", "build_filters"]