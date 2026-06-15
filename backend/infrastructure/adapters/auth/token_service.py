"""JWT token minting and validation adapter."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from application.ports.token_service import TokenService


class JwtTokenService(TokenService):
    def __init__(self, secret_key: str, expiry_hours: int = 24) -> None:
        self._secret_key = secret_key
        self._expiry_hours = expiry_hours

    def create_token(self, user_id: UUID) -> str:
        exp = datetime.now(UTC) + timedelta(hours=self._expiry_hours)
        return jwt.encode(
            {"sub": str(user_id), "exp": exp},
            self._secret_key,
            algorithm="HS256",
        )

    def decode_token(self, token: str) -> UUID | None:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError:
            return None

        sub = payload.get("sub")
        if not isinstance(sub, str):
            return None

        try:
            return UUID(sub)
        except ValueError:
            return None
