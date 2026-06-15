from typing import Protocol
from uuid import UUID


class TokenService(Protocol):
    def create_token(self, user_id: UUID) -> str: ...

    def decode_token(self, token: str) -> UUID | None: ...
