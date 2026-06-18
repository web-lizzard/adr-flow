"""HTTP request logging middleware."""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from application.logging import get_logger

_logger = get_logger(__name__)

_SKIP_PATHS = frozenset({"/health", "/api/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path

        _logger.info(
            "http.request_completed",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
