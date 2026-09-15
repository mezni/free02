"""Converters between domain models and SQLAlchemy ORM models.

No dependency on `src.ingestion.pipeline` to avoid import cycles.
"""

from src.db.models import (
    Chunk as ChunkORM,
)
from src.db.models import (
    DocumentRecord as DocumentRecordORM,
)
from src.domain.models.chunk import Chunk as DomainChunk
from src.domain.models.document import (
    DiscoveredDocument,
    FileState,
    SourceType,
)
from src.domain.models.document import (
    DocumentRecord as DomainDocumentRecord,
)


def document_to_orm(record: DomainDocumentRecord) -> DocumentRecordORM:
    doc = record.discovered_doc
    return DocumentRecordORM(
        doc_id=record.doc_id,
        version=record.version,
        version_tag=record.version_tag,
        is_active=record.is_active,
        state=record.state.value if isinstance(record.state, FileState) else str(record.state),
        tenant_id=record.tenant_id,
        access_roles=list(record.access_roles),
        classification=record.classification,
        department=record.department,
        category=record.category,
        relative_path=doc.relative_path,
        file_name=doc.file_name,
        parent_directory=doc.parent_directory,
        file_extension=doc.file_extension,
        mime_type=doc.mime_type,
        file_hash=doc.file_hash,
        checksum_algorithm=doc.checksum_algorithm,
        size_bytes=doc.size_bytes,
        modified_at=doc.modified_at,
        source=doc.source.value if isinstance(doc.source, SourceType) else str(doc.source),
    )


def document_from_orm(record: DocumentRecordORM) -> DomainDocumentRecord:
    return DomainDocumentRecord(
        doc_id=record.doc_id,
        version=record.version,
        version_tag=record.version_tag,
        is_active=record.is_active,
        state=FileState(record.state),
        tenant_id=record.tenant_id,
        access_roles=list(record.access_roles or []),
        classification=record.classification,
        department=record.department,
        category=record.category,
        discovered_doc=DiscoveredDocument(
            relative_path=record.relative_path,
            file_name=record.file_name,
            parent_directory=record.parent_directory,
            file_extension=record.file_extension,
            mime_type=record.mime_type,
            file_hash=record.file_hash,
            checksum_algorithm=record.checksum_algorithm,
            size_bytes=record.size_bytes,
            modified_at=record.modified_at,
            source=SourceType(record.source),
        ),
    )


def chunk_to_orm(chunk: DomainChunk, embedding: list[float]) -> ChunkORM:
    metadata = chunk.get_vector_metadata()
    return ChunkORM(
        chunk_id=chunk.id,
        run_id=chunk.run_id,
        doc_id=chunk.doc_id,
        relative_path=str(metadata.get("relative_path", "")),
        version=int(metadata.get("version", 1)),
        chunk_index=chunk.index,
        content=chunk.content,
        doc_metadata=metadata,
        is_active=bool(metadata.get("is_active", True)),
        embedding=embedding,
    )


__all__ = [
    "chunk_to_orm",
    "document_from_orm",
    "document_to_orm",
]