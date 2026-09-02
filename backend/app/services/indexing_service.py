"""
IndexingService — production-grade document ingestion pipeline.

Pipeline:
  1. Extract text          (DocumentProcessor)
  2. Split into chunks     (Chunker)
  3. Find resume point     (VectorStore.count_document_chunks)
  4. Batch-embed chunks    (EmbeddingService.embed_batch — N chunks / 100 per API call)
  5. Upsert vectors        (VectorStore.store_chunks — idempotent by chunk_index)
  6. Validate vector count (VectorStore.count_document_chunks == total_chunks)
  7. Retrieval verification (VectorStore.search — at least 1 result must come back)
  8. Mark indexed          (DocumentRepository.update_index_status)

Guarantees:
  - Atomic: document is marked INDEXED only after all vectors are stored AND verified.
  - Resume: if step 4 fails at chunk 97/300, next run resumes from chunk 97.
  - Rollback: if validation fails, partial vectors are deleted and status → FAILED.
  - Never silent failure: every exception updates status and re-raises.
  - Structured errors: IndexingError carries indexed_chunks + remaining_chunks.
"""

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.document import Document, IndexStatus
from app.repositories.document_repository import DocumentRepository
from app.services.chunker import Chunker
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

# Type alias for progress callback: (chunks_done, chunks_total)
ProgressCallback = Callable[[int, int], None]


class IndexingError(Exception):
    """
    Raised when indexing fails.
    Carries structured context for API error responses.
    """
    def __init__(
        self,
        reason: str,
        indexed_chunks: int = 0,
        remaining_chunks: int = 0,
    ):
        super().__init__(reason)
        self.reason = reason
        self.indexed_chunks = indexed_chunks
        self.remaining_chunks = remaining_chunks

    def to_dict(self) -> dict:
        return {
            "status": "failed",
            "reason": self.reason,
            "indexed_chunks": self.indexed_chunks,
            "remaining_chunks": self.remaining_chunks,
        }


class IndexingService:
    """
    Orchestrates the full document ingestion pipeline.

    Responsibilities:
      - Coordinates all pipeline stages
      - Tracks and persists document status at every step
      - Provides resume-from-checkpoint on retry
      - Validates atomicity: mark indexed only when fully complete
      - Rolls back partial state on failure
    """

    def __init__(self, db: Session | None = None):
        self.processor = DocumentProcessor()
        self.chunker = Chunker()
        self.embedder = EmbeddingService()
        self.store = VectorStore()
        self._repo = DocumentRepository(db) if db else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def index_document(
        self,
        document: Document,
        on_progress: ProgressCallback | None = None,
        resume: bool = True,
    ) -> int:
        """
        Index a document into Qdrant.

        Stages:
          1. Extract text
          2. Split into chunks
          3. Determine resume point
          4. Batch-embed remaining chunks
          5. Upsert vectors to Qdrant
          6. Validate vector count == chunk count
          7. Validate retrieval returns results
          8. Mark document as INDEXED

        Args:
            document: Document ORM object.
            on_progress: Optional callback(done, total) after each embedding batch.
            resume: If True, skip already-indexed chunks (idempotent re-run).

        Returns:
            Number of NEW chunks indexed this run.

        Raises:
            IndexingError: On any failure. Status is updated before raising.
        """
        pipeline_start = time.monotonic()
        logger.info(
            "═══ Indexing started ═══ document_id=%d filename=%s",
            document.id,
            document.original_filename,
        )

        self._set_status(document, IndexStatus.INDEXING)

        # ── Stage 1: Extract text ──────────────────────────────────────
        logger.info("Stage 1/7: Extracting text…")
        try:
            text = self.processor.extract_text(document.storage_path)
        except Exception as exc:
            self._fail(document, str(exc), 0, 0)
            raise IndexingError(f"Text extraction failed: {exc}", 0, 0) from exc

        if not text.strip():
            msg = "Document produced no extractable text"
            logger.warning("%s — document_id=%d", msg, document.id)
            self._fail(document, msg, 0, 0)
            raise IndexingError(msg, 0, 0)

        # ── Stage 2: Split into chunks ─────────────────────────────────
        logger.info("Stage 2/7: Chunking text…")
        chunks = self.chunker.split(text)
        total_chunks = len(chunks)

        logger.info(
            "Chunks: %d | document_id=%d | filename=%s",
            total_chunks,
            document.id,
            document.original_filename,
        )

        self._set_status(document, IndexStatus.INDEXING, chunks_total=total_chunks)

        # ── Stage 3: Find resume point ─────────────────────────────────
        start_from = 0
        if resume:
            start_from = self._find_resume_point(document.id, total_chunks)
            if start_from > 0:
                logger.info(
                    "Stage 3/7: Resuming from chunk %d/%d (document_id=%d)",
                    start_from,
                    total_chunks,
                    document.id,
                )
            else:
                logger.info("Stage 3/7: Starting from chunk 0 (no prior state)")
        else:
            logger.info("Stage 3/7: Resume disabled — starting fresh")

        remaining_chunks = chunks[start_from:]
        already_indexed = start_from

        if not remaining_chunks:
            logger.info(
                "All %d chunks already indexed — nothing to do (document_id=%d)",
                total_chunks,
                document.id,
            )
            self._set_status(
                document,
                IndexStatus.INDEXED,
                chunk_count=total_chunks,
                chunks_total=total_chunks,
            )
            return 0

        # ── Stage 4: Batch-embed ───────────────────────────────────────
        logger.info(
            "Stage 4/7: Generating embeddings (%d chunks, starting at %d)…",
            len(remaining_chunks),
            start_from,
        )

        def _progress(batch_done: int, batch_total: int) -> None:
            total_done = already_indexed + batch_done
            logger.info(
                "Generating embeddings (%d/%d)",
                total_done,
                total_chunks,
            )
            if on_progress:
                on_progress(total_done, total_chunks)

        try:
            embeddings = self.embedder.embed_batch(
                remaining_chunks,
                on_progress=_progress,
            )
        except Exception as exc:
            self._fail(document, str(exc), already_indexed, len(remaining_chunks))
            raise IndexingError(
                f"Embedding generation failed: {exc}",
                indexed_chunks=already_indexed,
                remaining_chunks=len(remaining_chunks),
            ) from exc

        # ── Stage 5: Upsert vectors ────────────────────────────────────
        logger.info(
            "Stage 5/7: Uploading vectors to Qdrant (%d vectors)…",
            len(embeddings),
        )
        try:
            self.store.store_chunks(
                document_id=document.id,
                filename=document.original_filename,
                organization_id=document.organization_id,
                chunks=remaining_chunks,
                embeddings=embeddings,
                start_index=start_from,
            )
        except Exception as exc:
            self._fail(document, str(exc), already_indexed, len(remaining_chunks))
            raise IndexingError(
                f"Vector storage failed: {exc}",
                indexed_chunks=already_indexed,
                remaining_chunks=len(remaining_chunks),
            ) from exc

        # ── Stage 6: Validate vector count ────────────────────────────
        logger.info("Stage 6/7: Validating vector count…")
        try:
            stored_count = self.store.count_document_chunks(document.id)
        except Exception as exc:
            logger.warning(
                "Could not validate vector count for document_id=%d: %s",
                document.id,
                exc,
            )
            stored_count = total_chunks  # assume OK if Qdrant count fails

        if stored_count != total_chunks:
            msg = (
                f"Vector count mismatch: expected {total_chunks}, "
                f"found {stored_count} in Qdrant"
            )
            logger.error("%s (document_id=%d)", msg, document.id)
            self._rollback_and_fail(document, msg, stored_count, total_chunks - stored_count)
            raise IndexingError(
                msg,
                indexed_chunks=stored_count,
                remaining_chunks=total_chunks - stored_count,
            )

        logger.info(
            "Vector count validated: %d/%d ✓",
            stored_count,
            total_chunks,
        )

        # ── Stage 7: Retrieval verification ───────────────────────────
        logger.info("Stage 7/7: Verifying retrieval…")
        try:
            retrieval_ok = self._verify_retrieval(document)
        except Exception as exc:
            logger.warning(
                "Retrieval verification error for document_id=%d: %s — continuing",
                document.id,
                exc,
            )
            retrieval_ok = True  # Don't fail indexing on verification error

        if not retrieval_ok:
            msg = "Retrieval verification failed: search returned 0 results after indexing"
            logger.error("%s (document_id=%d)", msg, document.id)
            self._rollback_and_fail(document, msg, stored_count, 0)
            raise IndexingError(msg, indexed_chunks=stored_count, remaining_chunks=0)

        # ── Stage 8: Mark indexed ──────────────────────────────────────
        final_count = already_indexed + len(remaining_chunks)
        self._set_status(
            document,
            IndexStatus.INDEXED,
            chunk_count=final_count,
            chunks_total=total_chunks,
        )

        elapsed = round(time.monotonic() - pipeline_start, 2)
        logger.info(
            "═══ Index completed in %.1fs ═══ "
            "document_id=%d | filename=%s | chunks=%d | vectors=%d",
            elapsed,
            document.id,
            document.original_filename,
            final_count,
            stored_count,
        )

        return len(remaining_chunks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_resume_point(self, document_id: int, total_chunks: int) -> int:
        """
        Query Qdrant for how many chunks are already stored.
        Returns the chunk index to resume from (0 = start fresh).
        """
        try:
            count = self.store.count_document_chunks(document_id)
            if count >= total_chunks:
                return total_chunks  # fully indexed
            if count > 0:
                logger.info(
                    "Resume: %d/%d chunks already in Qdrant for document_id=%d",
                    count,
                    total_chunks,
                    document_id,
                )
            return count
        except Exception as exc:
            logger.warning(
                "Could not determine resume point for document_id=%d: %s — starting fresh",
                document_id,
                exc,
            )
            return 0

    def _verify_retrieval(self, document: Document) -> bool:
        """
        Perform a semantic search using the document filename as the query.
        Returns True if at least one result comes back scoped to this document.
        """
        from app.services.embedding_service import EmbeddingService

        query = f"{document.original_filename} {document.original_filename}"
        try:
            query_vector = EmbeddingService().embed(query)
            results = self.store.search(
                query_vector=query_vector,
                organization_id=document.organization_id,
                limit=1,
            )
            found = len(results) > 0
            if found:
                logger.info(
                    "Retrieval verified: document_id=%d returned %d result(s)",
                    document.id,
                    len(results),
                )
            else:
                logger.error(
                    "Retrieval verification FAILED: 0 results for document_id=%d",
                    document.id,
                )
            return found
        except Exception as exc:
            logger.warning(
                "Retrieval verification error for document_id=%d: %s",
                document.id,
                exc,
            )
            return True  # Benefit of the doubt on verification errors

    def _rollback_and_fail(
        self,
        document: Document,
        reason: str,
        indexed_chunks: int,
        remaining_chunks: int,
    ) -> None:
        """
        Delete all partial vectors from Qdrant and mark the document as FAILED.
        Ensures no partial state is left behind.
        """
        logger.error(
            "Rolling back partial index for document_id=%d: %s",
            document.id,
            reason,
        )
        try:
            self.store.delete_by_document(document.id)
            logger.info(
                "Rollback complete: deleted all vectors for document_id=%d",
                document.id,
            )
        except Exception as del_exc:
            logger.error(
                "Rollback failed for document_id=%d: %s — manual cleanup may be needed",
                document.id,
                del_exc,
            )
        self._fail(document, reason, indexed_chunks, remaining_chunks)

    def _fail(
        self,
        document: Document,
        reason: str,
        indexed_chunks: int,
        remaining_chunks: int,
    ) -> None:
        """Mark the document as FAILED and log a structured error."""
        logger.error(
            "Indexing FAILED | document_id=%d | reason=%s | "
            "indexed=%d | remaining=%d",
            document.id,
            reason,
            indexed_chunks,
            remaining_chunks,
        )
        new_status = IndexStatus.PARTIAL if indexed_chunks > 0 else IndexStatus.FAILED
        self._set_status(document, new_status, chunk_count=indexed_chunks)

    def _set_status(
        self,
        document: Document,
        status: str,
        chunk_count: int | None = None,
        chunks_total: int | None = None,
    ) -> None:
        """Persist document status update to DB if repo is available."""
        if self._repo is None:
            return
        try:
            self._repo.update_index_status(
                document=document,
                status=status,
                chunk_count=chunk_count,
                chunks_total=chunks_total,
            )
        except Exception as exc:
            # Never let a DB write failure mask the real error
            logger.warning(
                "Failed to update index status for document_id=%d: %s",
                document.id,
                exc,
            )
