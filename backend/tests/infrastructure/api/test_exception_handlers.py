"""Global domain error handler tests."""

from domain.errors import (
    AdrInvalidRetryStatus,
    InternalError,
    RetryableInternalError,
)
from fastapi import Request
from infrastructure.api.exception_handlers import domain_error_handler


def _request() -> Request:
    return Request({"type": "http", "path": "/api/test"})


def test_domain_error_handler_maps_internal_error_to_500() -> None:
    response = domain_error_handler(
        _request(),
        InternalError("Section Context has no body"),
    )

    assert response.status_code == 500
    assert (
        response.body
        == b'{"kind":"internal_error","message":"Section Context has no body"}'
    )


def test_domain_error_handler_maps_retryable_internal_error_to_502() -> None:
    response = domain_error_handler(
        _request(),
        RetryableInternalError("LLM provider unavailable"),
    )

    assert response.status_code == 502
    assert response.body == (
        b'{"kind":"retryable_internal_error","message":"LLM provider unavailable"}'
    )


def test_domain_error_handler_maps_guard_errors_to_400() -> None:
    response = domain_error_handler(_request(), AdrInvalidRetryStatus())

    assert response.status_code == 400
    assert response.body == (
        b'{"kind":"adr_invalid_retry_status",'
        b'"message":"ADR can only be retried from review_failed status"}'
    )
