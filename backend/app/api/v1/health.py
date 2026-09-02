from fastapi import APIRouter
from sqlalchemy import text

from app.config.settings import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """
    Deep health check — probes every critical dependency.
    Returns 200 if all healthy, 503 if any dependency is down.
    """
    checks: dict[str, str] = {}
    healthy = True

    # --- PostgreSQL ---
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check — database failed: %s", exc)
        checks["database"] = "error"
        healthy = False

    # --- Qdrant ---
    try:
        VectorStore().client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as exc:
        logger.error("Health check — qdrant failed: %s", exc)
        checks["qdrant"] = "error"
        healthy = False

    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "service": settings.app_name,
            "version": settings.app_version,
            "checks": checks,
        },
    )
