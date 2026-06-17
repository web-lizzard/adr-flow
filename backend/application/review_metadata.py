"""Review metadata value objects shared across application and API layers."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReviewErrorMetadata:
    source_event_id: UUID
    code: str
    message: str
    failed_at: datetime
