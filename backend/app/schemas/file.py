import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums.file_type import FileType

# A single path segment: no slashes, no "..", no leading/trailing whitespace, no
# null bytes. Because names never contain a separator, nothing built from this
# field can ever encode a directory-traversal sequence.
_NAME_PATTERN = re.compile(r"^[^/\\\x00]+$")


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not stripped or stripped != name:
        raise ValueError("name must not be empty or have leading/trailing whitespace")
    if stripped in (".", ".."):
        raise ValueError("name must not be '.' or '..'")
    if not _NAME_PATTERN.match(stripped):
        raise ValueError("name must not contain '/', '\\', or null bytes")
    return stripped


class FileCreate(BaseModel):
    parent_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    type: FileType
    content: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _validate_name(value)


class FileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    content: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return _validate_name(value) if value is not None else None


class FileTreeNode(BaseModel):
    """Lightweight metadata for rendering the file tree — no content payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    type: FileType
    created_at: datetime
    updated_at: datetime


class FileResponse(FileTreeNode):
    content: str | None
