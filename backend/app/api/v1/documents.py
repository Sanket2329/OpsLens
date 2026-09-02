"""
Documents API — upload, list, delete, reindex.

Upload flow:
  POST /upload        — save file + index (blocking, returns DocumentResponse)
  POST /upload/stream — save file + index with SSE progress stream

Reindex:
  POST /{id}/reindex  — resume indexing from last successful chunk
"""

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.dependencies import get_db
from app.schemas.document import DocumentResponse
from app.security.dependencies import get_current_user, require_admin
from app.services.document_service import DocumentService
from app.services.indexing_service import IndexingError, IndexingService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a document",
)
def upload_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document and index it into Qdrant.

    The document record is always created even if indexing fails,
    so the user can retry via POST /{id}/reindex.
    """
    service = DocumentService(db)

    try:
        document = service.save_file(
            file=file,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    try:
        from app.tasks.document_tasks import index_document_task
        index_document_task.delay(document.id)
        logger.info(
            "Document uploaded and indexing enqueued: id=%d",
            document.id,
        )
    except Exception as exc:
        logger.error(
            "Unexpected error enqueuing index task for document_id=%d: %s",
            document.id,
            exc,
            exc_info=True,
        )

    db.refresh(document)
    return document


@router.post(
    "/upload/stream",
    summary="Upload and index a document with SSE progress updates",
    response_class=StreamingResponse,
)
def upload_document_stream(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document and stream indexing progress via Server-Sent Events.

    SSE event types:
      {"type": "saved",    "document_id": N, "filename": "..."}
      {"type": "progress", "chunks_done": N, "chunks_total": M, "pct": P}
      {"type": "done",     "document_id": N, "chunk_count": N, "index_status": "indexed"}
      {"type": "error",    "detail": "...", "indexed_chunks": N, "remaining_chunks": M}
    """
    service = DocumentService(db)

    def event_stream():
        # ── Save file ──────────────────────────────────────────────────
        try:
            document = service.save_file(
                file=file,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
            )
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc), 'indexed_chunks': 0, 'remaining_chunks': 0})}\n\n"
            return
        except Exception as exc:
            logger.error("File save failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'detail': 'File upload failed', 'indexed_chunks': 0, 'remaining_chunks': 0})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'saved', 'document_id': document.id, 'filename': document.original_filename})}\n\n"

        # ── Index with progress ────────────────────────────────────────
        # Collect progress events into a list (can't yield from nested fn)
        progress_events: list[str] = []

        def _on_progress(done: int, total: int) -> None:
            progress_events.append(json.dumps({
                "type": "progress",
                "chunks_done": done,
                "chunks_total": total,
                "pct": round((done / total) * 100) if total else 0,
            }))

        try:
            IndexingService(db=db).index_document(document, on_progress=_on_progress)
        except IndexingError as exc:
            for evt in progress_events:
                yield f"data: {evt}\n\n"
            yield f"data: {json.dumps({'type': 'error', **exc.to_dict()})}\n\n"
            db.refresh(document)
            return
        except Exception as exc:
            logger.error(
                "Unexpected stream indexing error document_id=%d: %s",
                document.id,
                exc,
                exc_info=True,
            )
            for evt in progress_events:
                yield f"data: {evt}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc), 'indexed_chunks': 0, 'remaining_chunks': 0})}\n\n"
            db.refresh(document)
            return

        for evt in progress_events:
            yield f"data: {evt}\n\n"

        db.refresh(document)
        yield f"data: {json.dumps({'type': 'done', 'document_id': document.id, 'chunk_count': document.chunk_count, 'chunks_total': document.chunks_total, 'index_status': document.index_status})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List all documents for the current organisation",
)
def list_documents(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    return service.list(organization_id=current_user.organization_id)


@router.get(
    "/{document_id}/download",
    summary="Download the original document file",
)
def download_document(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse
    import os

    service = DocumentService(db)
    document = service.get(
        document_id=document_id,
        organization_id=current_user.organization_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not document.storage_path or not os.path.exists(document.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk",
        )

    return FileResponse(
        path=document.storage_path,
        filename=document.original_filename,
        media_type=document.content_type,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and remove its vectors from Qdrant",
)
def delete_document(
    document_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)
    deleted = service.delete(
        document_id=document_id,
        organization_id=current_user.organization_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


@router.post(
    "/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-index a document — resumes from last successful chunk",
)
def reindex_document(
    document_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-run indexing for a document.

    If the previous run failed at chunk 97/300, this resumes from chunk 97.
    If the document was fully indexed, this is a no-op.

    Returns:
        {"document_id": N, "new_chunks_indexed": N, "total_chunks": N, "index_status": "..."}
    """
    service = DocumentService(db)
    document = service.get(
        document_id=document_id,
        organization_id=current_user.organization_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        from app.tasks.document_tasks import index_document_task
        index_document_task.delay(document.id)
    except Exception as exc:
        logger.error(
            "Unexpected error enqueuing reindex task document_id=%d: %s",
            document_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "failed", "reason": str(exc), "indexed_chunks": 0, "remaining_chunks": 0},
        )

    db.refresh(document)
    return {
        "document_id": document_id,
        "enqueued": True,
        "total_chunks": document.chunk_count,
        "index_status": document.index_status,
    }
