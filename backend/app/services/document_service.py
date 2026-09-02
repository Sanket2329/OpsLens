import os
import shutil
import uuid

from fastapi import UploadFile

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

_MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


class DocumentService:
    def __init__(self, db):
        self.db = db
        self.repo = DocumentRepository(db)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list(self, organization_id: int) -> list[Document]:
        return self.repo.list_by_organization(organization_id)

    def get(self, document_id: int, organization_id: int) -> Document | None:
        return self.repo.get_by_id_scoped(
            document_id=document_id,
            organization_id=organization_id,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def save_file(
        self,
        file: UploadFile,
        organization_id: int,
        user_id: int,
    ) -> Document:
        self._validate_file(file)

        os.makedirs(settings.upload_dir, exist_ok=True)

        extension = os.path.splitext(file.filename or "")[1].lower()
        filename = f"{uuid.uuid4()}{extension}"
        storage_path = os.path.join(settings.upload_dir, filename)

        try:
            with open(storage_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = os.path.getsize(storage_path)

            document = self.repo.create(
                Document(
                    filename=filename,
                    original_filename=file.filename,
                    content_type=file.content_type,
                    file_size=file_size,
                    storage_path=storage_path,
                    organization_id=organization_id,
                    uploaded_by=user_id,
                )
            )

            logger.info(
                "Document saved: id=%d filename=%s size=%d org_id=%d",
                document.id,
                file.filename,
                file_size,
                organization_id,
            )

            return document

        except Exception:
            # Clean up the file if the DB write fails
            if os.path.exists(storage_path):
                os.remove(storage_path)
                logger.warning("Cleaned up orphaned file: %s", storage_path)
            raise

    def delete(self, document_id: int, organization_id: int) -> bool:
        """
        Delete a document from the database, disk, and Qdrant.
        Returns True if deleted, False if not found.
        """
        document = self.repo.get_by_id_scoped(
            document_id=document_id,
            organization_id=organization_id,
        )

        if document is None:
            return False

        # Remove vectors from Qdrant (best-effort — don't fail delete if Qdrant is down)
        try:
            VectorStore().delete_by_document(document_id=document_id)
        except Exception as exc:
            logger.warning(
                "Failed to remove Qdrant vectors for document id=%d: %s",
                document_id,
                exc,
            )

        # Remove file from disk (best-effort)
        if document.storage_path and os.path.exists(document.storage_path):
            try:
                os.remove(document.storage_path)
                logger.info("Deleted file: %s", document.storage_path)
            except OSError as exc:
                logger.warning("Could not delete file %s: %s", document.storage_path, exc)

        # Remove from DB
        self.repo.delete(document)

        logger.info(
            "Document deleted: id=%d org_id=%d", document_id, organization_id
        )

        return True

    # ------------------------------------------------------------------
    # Private validation
    # ------------------------------------------------------------------

    def _validate_file(self, file: UploadFile) -> None:
        if not file.filename:
            raise ValueError("Filename is required")

        extension = os.path.splitext(file.filename)[1].lower()

        if extension not in settings.allowed_extensions_list:
            raise ValueError(
                f"Unsupported file type '{extension}'. "
                f"Allowed: {', '.join(settings.allowed_extensions_list)}"
            )

        if file.size is not None and file.size > _MAX_BYTES:
            raise ValueError(
                f"File too large. Maximum allowed size is {settings.max_upload_size_mb} MB."
            )
