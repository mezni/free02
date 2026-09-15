"""Document record repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import DocumentRecord
from src.db.repositories.upsert import upsert


class DocumentRepository:
    """CRUD + lifecycle queries for the versioned document registry."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: DocumentRecord) -> DocumentRecord:
        self._session.add(document)
        return document

    def upsert(self, document: DocumentRecord) -> DocumentRecord:
        upsert(self._session, DocumentRecord, document, "doc_id")
        return document

    def get(self, doc_id: str) -> DocumentRecord | None:
        return self._session.get(DocumentRecord, doc_id)

    def get_by_file(self, relative_path: str) -> list[DocumentRecord]:
        stmt = (
            select(DocumentRecord)
            .where(DocumentRecord.relative_path == relative_path)
            .order_by(DocumentRecord.version.desc())
        )
        return list(self._session.scalars(stmt))

    def list_active(self) -> list[DocumentRecord]:
        stmt = select(DocumentRecord).where(DocumentRecord.is_active.is_(True))
        return list(self._session.scalars(stmt))

    def list_all(self) -> list[DocumentRecord]:
        return list(self._session.scalars(select(DocumentRecord)))

    def deactivate(self, doc_id: str) -> DocumentRecord | None:
        document = self.get(doc_id)
        if document is not None:
            document.is_active = False
        return document