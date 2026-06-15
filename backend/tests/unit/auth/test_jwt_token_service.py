"""Unit tests for JwtTokenService decode rejection guarantees."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from infrastructure.adapters.auth.token_service import JwtTokenService

_SECRET = "test-jwt-secret-at-least-32-characters"
_OTHER_SECRET = "other-jwt-secret-also-32-chars-min"


def _service(secret: str = _SECRET, expiry_hours: int = 24) -> JwtTokenService:
    return JwtTokenService(secret_key=secret, expiry_hours=expiry_hours)


def _future_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def _past_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def test_create_and_decode_round_trip_returns_same_user_id() -> None:
    user_id = uuid4()
    service = _service()

    token = service.create_token(user_id)

    assert service.decode_token(token) == user_id


def test_decode_rejects_expired_token() -> None:
    user_id = uuid4()
    expired_token = jwt.encode(
        {"sub": str(user_id), "exp": _past_exp()},
        _SECRET,
        algorithm="HS256",
    )

    assert _service().decode_token(expired_token) is None


def test_decode_rejects_token_signed_with_wrong_secret() -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "exp": _future_exp()},
        _OTHER_SECRET,
        algorithm="HS256",
    )

    assert _service(secret=_SECRET).decode_token(token) is None


def test_decode_rejects_malformed_token_string() -> None:
    assert _service().decode_token("not.a.jwt.at.all") is None


def test_decode_rejects_empty_token_string() -> None:
    assert _service().decode_token("") is None


def test_decode_rejects_tampered_payload() -> None:
    user_id = uuid4()
    token = _service().create_token(user_id)
    header, payload, signature = token.split(".", 2)

    payload_bytes = bytearray(base64.urlsafe_b64decode(payload + "=="))
    payload_bytes[0] ^= 0x01
    tampered_payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()

    tampered_token = f"{header}.{tampered_payload}.{signature}"

    assert _service().decode_token(tampered_token) is None


def test_decode_rejects_missing_sub_claim() -> None:
    token = jwt.encode(
        {"exp": _future_exp()},
        _SECRET,
        algorithm="HS256",
    )

    assert _service().decode_token(token) is None


def test_decode_rejects_non_uuid_sub_claim() -> None:
    token = jwt.encode(
        {"sub": "not-a-uuid", "exp": _future_exp()},
        _SECRET,
        algorithm="HS256",
    )

    assert _service().decode_token(token) is None


def test_decode_rejects_non_string_sub_claim() -> None:
    token = jwt.encode(
        {"sub": 12345, "exp": _future_exp()},
        _SECRET,
        algorithm="HS256",
    )

    assert _service().decode_token(token) is None
