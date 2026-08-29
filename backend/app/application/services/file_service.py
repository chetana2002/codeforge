import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.file_type import FileType
from app.domain.models.file import File
from app.schemas.envelope import ApiError
from app.schemas.file import FileCreate, FileUpdate


class FileService:
    """All operations are scoped to a single project (ownership of that project is
    verified by the caller via ProjectService.get_owned before reaching here)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tree(self, project_id: uuid.UUID) -> list[File]:
        result = await self.db.scalars(
            select(File).where(File.project_id == project_id).order_by(File.type, File.name)
        )
        return list(result.all())

    async def get(self, project_id: uuid.UUID, file_id: uuid.UUID) -> File:
        file = await self.db.scalar(
            select(File).where(File.id == file_id, File.project_id == project_id)
        )
        if file is None:
            raise ApiError(status_code=404, code="FILE_NOT_FOUND", message="File not found")
        return file

    async def _get_folder_or_raise(self, project_id: uuid.UUID, folder_id: uuid.UUID) -> File:
        folder = await self.get(project_id, folder_id)
        if folder.type != FileType.FOLDER:
            raise ApiError(
                status_code=400,
                code="PARENT_NOT_A_FOLDER",
                message="The specified parent is not a folder",
            )
        return folder

    async def _would_create_cycle(
        self, project_id: uuid.UUID, file_id: uuid.UUID, new_parent_id: uuid.UUID
    ) -> bool:
        """True if new_parent_id is file_id itself or one of its descendants —
        moving into either would create a cycle in the tree."""
        current: uuid.UUID | None = new_parent_id
        while current is not None:
            if current == file_id:
                return True
            parent = await self.db.scalar(
                select(File.parent_id).where(File.id == current, File.project_id == project_id)
            )
            current = parent
        return False

    async def create(self, project_id: uuid.UUID, payload: FileCreate) -> File:
        if payload.type == FileType.FOLDER and payload.content is not None:
            raise ApiError(
                status_code=400,
                code="FOLDER_CANNOT_HAVE_CONTENT",
                message="Folders cannot have file content",
            )

        if payload.parent_id is not None:
            await self._get_folder_or_raise(project_id, payload.parent_id)

        file = File(
            project_id=project_id,
            parent_id=payload.parent_id,
            name=payload.name,
            type=payload.type,
            content=payload.content if payload.type == FileType.FILE else None,
        )
        self.db.add(file)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ApiError(
                status_code=409,
                code="FILE_ALREADY_EXISTS",
                message="A file or folder with that name already exists in this location",
            ) from exc
        await self.db.refresh(file)
        return file

    async def update(self, project_id: uuid.UUID, file_id: uuid.UUID, payload: FileUpdate) -> File:
        file = await self.get(project_id, file_id)
        updates = payload.model_dump(exclude_unset=True)

        if "content" in updates and file.type == FileType.FOLDER and updates["content"] is not None:
            raise ApiError(
                status_code=400,
                code="FOLDER_CANNOT_HAVE_CONTENT",
                message="Folders cannot have file content",
            )

        if "parent_id" in updates:
            new_parent_id = updates["parent_id"]
            if new_parent_id is not None:
                await self._get_folder_or_raise(project_id, new_parent_id)
                if await self._would_create_cycle(project_id, file_id, new_parent_id):
                    raise ApiError(
                        status_code=400,
                        code="INVALID_MOVE",
                        message="Cannot move a folder into itself or one of its own subfolders",
                    )

        for field, value in updates.items():
            setattr(file, field, value)

        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ApiError(
                status_code=409,
                code="FILE_ALREADY_EXISTS",
                message="A file or folder with that name already exists in this location",
            ) from exc
        await self.db.refresh(file)
        return file

    async def delete(self, project_id: uuid.UUID, file_id: uuid.UUID) -> None:
        file = await self.get(project_id, file_id)
        await self.db.delete(file)
        await self.db.flush()
