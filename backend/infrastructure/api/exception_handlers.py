"""Global FastAPI exception handlers for domain errors."""

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

_STATUS_BY_KIND: dict[str, int] = {
    AdrNotFound.kind: 404,
    AdrAccessDenied.kind: 403,
    AdrTitleAlreadyExists.kind: 409,
    InternalError.kind: 500,
    RetryableInternalError.kind: 502,
}


def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status_code = _STATUS_BY_KIND.get(exc.kind, 400)
    message = exc.message if exc.message is not None else exc.kind
    return JSONResponse(
        status_code=status_code,
        content={"kind": exc.kind, "message": message},
    )
