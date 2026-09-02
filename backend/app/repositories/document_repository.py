from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_id_scoped(
        self,
        document_id: int,
        organization_id: int,
    ) -> Document | None:
        """Fetch a document only if it belongs to the given organization."""
        return (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
            .first()
        )

    def update_index_status(
        self,
        document: Document,
        status: str,
        chunk_count: int | None = None,
        chunks_total: int | None = None,
    ) -> Document:
        document.index_status = status
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if chunks_total is not None:
            document.chunks_total = chunks_total
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()

    def list_by_organization(self, organization_id: int) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
            .all()
        )
