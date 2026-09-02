from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as document_router
from app.api.v1.health import router as health_router
from app.api.v1.incidents import router as incident_router
from app.api.v1.investigation import router as investigation_router
from app.config.settings import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.services.vector_store import VectorStore

configure_logging(level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logger.info("Starting OpsLens API v%s", settings.app_version)

    # Ensure Qdrant collection exists before handling any requests
    try:
        VectorStore().create_collection()
        logger.info("Qdrant collection ready")
    except Exception as exc:
        logger.error("Failed to initialise Qdrant collection: %s", exc)
        # Non-fatal — the collection may already exist or Qdrant may be
        # temporarily unavailable; let requests fail individually.

    yield

    logger.info("Shutting down OpsLens API")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Incident Investigation Platform",
    lifespan=lifespan,
    # Disable docs in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiter import limiter

# ---------------------------------------------------------------------------
# Middleware (order matters — outermost first)
# ---------------------------------------------------------------------------
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("ValueError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
API_PREFIX = "/api/v1"

app.include_router(health_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(document_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(incident_router, prefix=API_PREFIX)
app.include_router(investigation_router, prefix=API_PREFIX)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
