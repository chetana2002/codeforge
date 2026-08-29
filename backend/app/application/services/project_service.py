import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.project import Project
from app.schemas.envelope import ApiError
from app.schemas.pagination import PageParams
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """All operations are scoped to a single owner: a project belonging to another
    user is treated as not found, never as forbidden, to avoid confirming its
    existence to users who don't own it."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: uuid.UUID, payload: ProjectCreate) -> Project:
        project = Project(
            owner_id=owner_id,
            name=payload.name,
            description=payload.description,
            language=payload.language,
            visibility=payload.visibility,
        )
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def list_for_owner(
        self, owner_id: uuid.UUID, params: PageParams, search: str | None = None
    ) -> tuple[list[Project], int]:
        filters = [Project.owner_id == owner_id]
        if search:
            pattern = f"%{search}%"
            filters.append(or_(Project.name.ilike(pattern), Project.description.ilike(pattern)))

        total = await self.db.scalar(select(func.count()).select_from(Project).where(*filters))

        result = await self.db.scalars(
            select(Project)
            .where(*filters)
            .order_by(Project.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = list(result.all())
        return items, total or 0

    async def get_owned(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = await self.db.scalar(
            select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
        )
        if project is None:
            raise ApiError(status_code=404, code="PROJECT_NOT_FOUND", message="Project not found")
        return project

    async def update(
        self, owner_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate
    ) -> Project:
        project = await self.get_owned(owner_id, project_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def delete(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = await self.get_owned(owner_id, project_id)
        await self.db.delete(project)
        await self.db.flush()
