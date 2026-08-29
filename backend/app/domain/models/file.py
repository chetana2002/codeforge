import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.file_type import FileType
from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.domain.models.project import Project


class File(Base):
    """A file or folder in a project's tree. Structure is an adjacency list
    (parent_id + name) rather than a materialized path: renames/moves are then a
    single-row update with no cascading path rewrites, and sibling-name conflicts
    are enforced directly by the database via the partial unique indexes below."""

    __tablename__ = "files"
    __table_args__ = (
        Index(
            "ix_files_unique_root_name",
            "project_id",
            "name",
            unique=True,
            postgresql_where="parent_id IS NULL",
        ),
        Index(
            "ix_files_unique_child_name",
            "project_id",
            "parent_id",
            "name",
            unique=True,
            postgresql_where="parent_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[FileType] = mapped_column(
        SAEnum(
            FileType,
            name="file_type",
            native_enum=False,
            length=16,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="files")
