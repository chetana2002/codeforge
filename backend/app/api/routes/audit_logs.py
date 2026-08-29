from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.application.services.audit_service import list_for_user
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.audit_log import AuditLogResponse
from app.schemas.envelope import Envelope
from app.schemas.pagination import Page, PageParams

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=Envelope[Page[AuditLogResponse]])
async def list_my_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[Page[AuditLogResponse]]:
    """The current user's own audit trail — login/logout, project and file
    lifecycle events, execution lifecycle events — most recent first."""
    params = PageParams(page=page, page_size=page_size)
    items, total = await list_for_user(db, current_user.id, params)
    return Envelope(
        data=Page[AuditLogResponse].create(
            items=[AuditLogResponse.model_validate(item) for item in items],
            total=total,
            params=params,
        )
    )
