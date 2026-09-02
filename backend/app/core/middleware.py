"""
Request latency middleware.

Logs every request with method, path, status code, and elapsed time.
Attaches X-Request-ID and X-Response-Time headers to every response.
"""

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # Attach to request state so route handlers can reference it
        request.state.request_id = request_id

        response: Response = await call_next(request)

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

        # Skip logging health checks to keep logs clean
        if request.url.path != "/api/v1/health":
            logger.info(
                "%s %s %d %.1fms request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                request_id,
            )

        return response
