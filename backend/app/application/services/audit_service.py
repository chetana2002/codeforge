import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.audit_event import AuditEventType
from app.domain.models.audit_log import AuditLog
from app.schemas.pagination import PageParams


def record_audit_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: AuditEventType,
    *,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Stages an AuditLog row on the given session without committing.

    Callers add this to the same session/transaction as the action being
    recorded, so it lands atomically with whatever it's an audit trail of —
    committing separately would risk a logged event for an action that then
    rolled back, or vice versa.
    """
    db.add(
        AuditLog(
            user_id=user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
        )
    )


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, params: PageParams
) -> tuple[list[AuditLog], int]:
    filters = [AuditLog.user_id == user_id]

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters))

    result = await db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return list(result.all()), total or 0
