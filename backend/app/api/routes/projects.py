import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.application.services.audit_service import record_audit_event
from app.application.services.project_service import ProjectService
from app.core.rate_limit import project_create_rate_limit
from app.domain.enums.audit_event import AuditEventType
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.envelope import Envelope
from app.schemas.pagination import Page, PageParams
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=Envelope[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(project_create_rate_limit())],
)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ProjectResponse]:
    service = ProjectService(db)
    project = await service.create(current_user.id, payload)
    record_audit_event(
        db,
        current_user.id,
        AuditEventType.PROJECT_CREATED,
        resource_type="project",
        resource_id=project.id,
    )
    await db.commit()
    return Envelope(data=ProjectResponse.model_validate(project))


@router.get("", response_model=Envelope[Page[ProjectResponse]])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[Page[ProjectResponse]]:
    service = ProjectService(db)
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_for_owner(current_user.id, params, search=q)
    return Envelope(
        data=Page[ProjectResponse].create(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
            params=params,
        )
    )


@router.get("/{project_id}", response_model=Envelope[ProjectResponse])
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ProjectResponse]:
    service = ProjectService(db)
    project = await service.get_owned(current_user.id, project_id)
    return Envelope(data=ProjectResponse.model_validate(project))


@router.patch("/{project_id}", response_model=Envelope[ProjectResponse])
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ProjectResponse]:
    service = ProjectService(db)
    project = await service.update(current_user.id, project_id, payload)
    await db.commit()
    return Envelope(data=ProjectResponse.model_validate(project))


@router.delete("/{project_id}", response_model=Envelope[dict[str, bool]])
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[dict[str, bool]]:
    service = ProjectService(db)
    await service.delete(current_user.id, project_id)
    record_audit_event(
        db,
        current_user.id,
        AuditEventType.PROJECT_DELETED,
        resource_type="project",
        resource_id=project_id,
    )
    await db.commit()
    return Envelope(data={"deleted": True})
