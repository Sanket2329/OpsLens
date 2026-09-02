from app.worker import celery
from app.db.database import SessionLocal
from app.services.indexing_service import IndexingService, IndexingError
from app.repositories.document_repository import DocumentRepository
from app.core.logging import get_logger

logger = get_logger(__name__)

@celery.task(bind=True, max_retries=3)
def index_document_task(self, document_id: int):
    logger.info(f"Starting background indexing for document_id={document_id}")
    db = SessionLocal()
    try:
        document = DocumentRepository(db).get_by_id(document_id)
        if not document:
            logger.error(f"Document {document_id} not found for indexing")
            return

        new_chunks = IndexingService(db=db).index_document(document, resume=True)
        db.refresh(document)
        logger.info(f"Successfully indexed document_id={document_id}, chunks={new_chunks}")
        return {"status": "success", "chunks_indexed": new_chunks}

    except IndexingError as exc:
        logger.error(f"Indexing error for document_id={document_id}: {exc.to_dict()}")
        # We don't retry structural errors
        return {"status": "failed", "error": exc.to_dict()}
    except Exception as exc:
        logger.exception(f"Unexpected error indexing document_id={document_id}: {exc}")
        db.rollback()
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()
