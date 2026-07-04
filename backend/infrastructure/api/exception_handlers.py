"""Global FastAPI exception handlers for domain errors."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from domain.errors import (
    AdrAccessDenied,
    AdrNotFound,
    AdrTitleAlreadyExists,
    DomainError,
    InternalError,
    RetryableInternalError,
)

_logger = logging.getLogger(__name__)

_STATUS_BY_KIND: dict[str, int] = {
    AdrNotFound.kind: 404,
    AdrAccessDenied.kind: 403,
    AdrTitleAlreadyExists.kind: 409,
    InternalError.kind: 500,
    RetryableInternalError.kind: 502,
}

_GENERIC_SERVER_ERROR = "An internal error occurred"


def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status_code = _STATUS_BY_KIND.get(exc.kind, 400)

    if status_code >= 500:
        _logger.error(
            "domain_error.server",
            extra={"error_kind": exc.kind, "error_message": exc.message},
        )
        message = _GENERIC_SERVER_ERROR
    else:
        message = exc.message if exc.message is not None else exc.kind

    return JSONResponse(
        status_code=status_code,
        content={"kind": exc.kind, "message": message},
    )
