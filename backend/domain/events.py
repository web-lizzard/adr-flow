"""Base type for domain events."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    occurred_at: datetime
