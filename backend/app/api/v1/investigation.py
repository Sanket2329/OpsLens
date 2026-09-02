import json

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.logging import get_logger
from app.core.rate_limiter import limiter
from app.db.dependencies import get_db
from app.schemas.investigation import InvestigationHistoryResponse, InvestigationResponse
from app.security.dependencies import get_current_user
from app.services.investigation_service import InvestigationService
from app.services.report_service import render_markdown, render_pdf
from app.services.runbook_service import RunbookService
from app.services.similarity_service import find_similar_investigations

logger = get_logger(__name__)

router = APIRouter(
    prefix="/investigate",
    tags=["Investigation"],
)

@router.post(
    "/{incident_id}",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run an AI investigation on an incident",
)
@limiter.limit("5/minute")
def investigate(
    request: Request,
    incident_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)

    try:
        report = service.investigate(
            incident_id=incident_id,
            organization_id=current_user.organization_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error during investigation for incident_id=%d", incident_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Investigation failed due to an internal error. Please retry.",
        )

    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    return report


# ---------------------------------------------------------------------------
# Streaming investigation (Server-Sent Events)
# ---------------------------------------------------------------------------

@router.post(
    "/{incident_id}/stream",
    summary="Stream an AI investigation as Server-Sent Events",
    response_class=StreamingResponse,
)
@limiter.limit("5/minute")
def investigate_stream(
    request: Request,
    incident_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream the investigation report token-by-token via SSE.

    Each SSE event is a JSON object:
        data: {"type": "token", "content": "..."}
        data: {"type": "done", "report": {...}}
        data: {"type": "error", "detail": "..."}
    """
    service = InvestigationService(db)

    def event_stream():
        try:
            for chunk in service.investigate_stream(
                incident_id=incident_id,
                organization_id=current_user.organization_id,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        except Exception as exc:
            logger.exception("Stream error for incident_id=%d", incident_id)
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Internal error. Please retry.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Crew-based investigation (CrewAI multi-agent)
# ---------------------------------------------------------------------------

@router.post(
    "/{incident_id}/crew",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a deep multi-agent investigation using CrewAI (slower, higher quality)",
)
@limiter.limit("2/minute")
def investigate_crew(
    request: Request,
    incident_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs a 4-agent CrewAI investigation:
      1. Retriever  — searches knowledge base
      2. Analyst    — diagnoses root cause (evidence-only)
      3. Recommender — produces remediation steps
      4. Reporter   — formats structured JSON report

    Takes 30-90s depending on document count. Returns the same
    InvestigationReport shape as the standard investigation endpoint.
    """
    import os
    # CrewAI uses LiteLLM which reads GEMINI_API_KEY from environment
    os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)

    service = InvestigationService(db)

    try:
        report = service.investigate_with_crew(
            incident_id=incident_id,
            organization_id=current_user.organization_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception:
        logger.exception(
            "Crew investigation failed for incident_id=%d", incident_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Crew investigation failed. Try the standard investigation instead.",
        )

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return report


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get(
    "/history",
    response_model=list[InvestigationHistoryResponse],
    summary="List all past investigations for this organisation",
)
def list_investigations(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)
    return service.list_history(organization_id=current_user.organization_id)


@router.get(
    "/history/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Get a specific investigation report",
)
def get_investigation(
    investigation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)

    investigation = service.get_by_id(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
    )

    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    return investigation


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

@router.get(
    "/history/{investigation_id}/report.md",
    response_class=PlainTextResponse,
    summary="Get investigation report as formatted Markdown",
)
def get_investigation_markdown(
    investigation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)

    investigation = service.get_by_id(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
    )

    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    markdown = render_markdown(investigation)

    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="investigation-{investigation_id}.md"'
        },
    )


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

@router.get(
    "/history/{investigation_id}/report.pdf",
    summary="Get investigation report as a PDF",
)
def get_investigation_pdf(
    investigation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)

    investigation = service.get_by_id(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
    )

    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    try:
        pdf_bytes = render_pdf(investigation)
    except Exception as exc:
        logger.error("PDF render failed for investigation_id=%d: %s", investigation_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation failed. Use the Markdown export instead.",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="investigation-{investigation_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Delete investigation
# ---------------------------------------------------------------------------

@router.delete(
    "/history/{investigation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an investigation report",
)
def delete_investigation(
    investigation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InvestigationService(db)
    deleted = service.delete(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )


# ---------------------------------------------------------------------------
# Runbook generation (1 Gemini call — opt-in only)
# ---------------------------------------------------------------------------

class RunbookGenerateRequest(BaseModel):
    service: str = ""


@router.post(
    "/history/{investigation_id}/runbook",
    summary="Generate an operational runbook from this investigation (1 AI call)",
)
def generate_runbook(
    investigation_id: int,
    body: RunbookGenerateRequest = RunbookGenerateRequest(),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a structured operational runbook from a completed investigation.

    The runbook is:
    1. Generated by Gemini (1 LLM call — only triggered when you click this button)
    2. Saved as a document in your knowledge base
    3. Automatically indexed into Qdrant

    Future investigations on the same service will retrieve this runbook
    as evidence, improving confidence scores over time.
    """
    service = InvestigationService(db)
    investigation = service.get_by_id(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
    )
    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    incident_title = investigation.get("incident_summary", {}) or {}
    incident_title = incident_title.get("title", f"Incident #{investigation.get('incident_id', '?')}")
    svc = body.service or (investigation.get("incident_summary") or {}).get("affected_service", "unknown-service")

    try:
        runbook_svc = RunbookService(db=db)
        result = runbook_svc.generate_runbook(
            investigation=investigation,
            incident_title=incident_title,
            service=svc,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.exception("Runbook generation failed for investigation_id=%d", investigation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Runbook generation failed: {exc}",
        )

    return {
        "investigation_id": investigation_id,
        "document_id": result.get("document_id"),
        "chunks_indexed": result.get("chunks_indexed", 0),
        "runbook_preview": result.get("runbook_text", "")[:500],
        "message": "Runbook generated and indexed. Future investigations will use it as evidence.",
    }


# ---------------------------------------------------------------------------
# Similar investigations (0 tokens — cosine similarity on stored reports)
# ---------------------------------------------------------------------------

@router.get(
    "/history/{investigation_id}/similar",
    summary="Find past investigations similar to this one (0 AI tokens)",
)
def get_similar_investigations(
    investigation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find past investigations with similar root causes using TF-IDF cosine similarity.

    Compares root_cause + executive_summary text across all your org's investigations.
    No API calls — pure math on existing data.

    Returns up to 3 similar investigations with similarity scores.
    """
    similar = find_similar_investigations(
        investigation_id=investigation_id,
        organization_id=current_user.organization_id,
        db=db,
    )
    return {
        "investigation_id": investigation_id,
        "similar_investigations": similar,
        "count": len(similar),
    }
