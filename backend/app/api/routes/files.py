import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.application.services.audit_service import record_audit_event
from app.application.services.file_service import FileService
from app.application.services.project_service import ProjectService
from app.domain.enums.audit_event import AuditEventType
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.envelope import Envelope
from app.schemas.file import FileCreate, FileResponse, FileTreeNode, FileUpdate

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


@router.get("", response_model=Envelope[list[FileTreeNode]])
async def list_files(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[list[FileTreeNode]]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    files = await FileService(db).list_tree(project.id)
    return Envelope(data=[FileTreeNode.model_validate(f) for f in files])


@router.get("/{file_id}", response_model=Envelope[FileResponse])
async def get_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[FileResponse]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    file = await FileService(db).get(project.id, file_id)
    return Envelope(data=FileResponse.model_validate(file))


@router.post("", response_model=Envelope[FileResponse], status_code=status.HTTP_201_CREATED)
async def create_file(
    project_id: uuid.UUID,
    payload: FileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[FileResponse]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    file = await FileService(db).create(project.id, payload)
    record_audit_event(
        db,
        current_user.id,
        AuditEventType.FILE_CREATED,
        resource_type="file",
        resource_id=file.id,
    )
    await db.commit()
    return Envelope(data=FileResponse.model_validate(file))


@router.patch("/{file_id}", response_model=Envelope[FileResponse])
async def update_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    payload: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[FileResponse]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    file = await FileService(db).update(project.id, file_id, payload)
    await db.commit()
    return Envelope(data=FileResponse.model_validate(file))


@router.delete("/{file_id}", response_model=Envelope[dict[str, bool]])
async def delete_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[dict[str, bool]]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    await FileService(db).delete(project.id, file_id)
    record_audit_event(
        db,
        current_user.id,
        AuditEventType.FILE_DELETED,
        resource_type="file",
        resource_id=file_id,
    )
    await db.commit()
    return Envelope(data={"deleted": True})
