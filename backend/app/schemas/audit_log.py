import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.enums.audit_event import AuditEventType


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: AuditEventType
    resource_type: str | None
    resource_id: uuid.UUID | None
    ip_address: str | None
    details: dict[str, Any] | None
    created_at: datetime
