import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums.language import Language
from app.domain.enums.visibility import ProjectVisibility


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    language: Language = Language.PYTHON
    visibility: ProjectVisibility = ProjectVisibility.PRIVATE


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    language: Language | None = None
    visibility: ProjectVisibility | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    language: Language
    visibility: ProjectVisibility
    created_at: datetime
    updated_at: datetime
