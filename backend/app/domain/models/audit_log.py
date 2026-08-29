import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums.audit_event import AuditEventType
from app.infrastructure.database.base import Base


class AuditLog(Base):
    """An append-only record of security- and resource-relevant actions.

    resource_type/resource_id identify what the event acted on (e.g.
    resource_type="project", resource_id=<project.id>) without a real foreign
    key: the referenced row can be deleted (a PROJECT_DELETED event is exactly
    that case) while the audit record must still exist afterward, so an FK
    with any ondelete behavior would either block the delete or destroy the
    evidence of it.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(
            AuditEventType,
            name="audit_event_type",
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
