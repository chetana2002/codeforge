import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums.execution_status import ExecutionStatus
from app.domain.enums.language import Language


class ExecuteRequest(BaseModel):
    file_id: uuid.UUID


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_id: uuid.UUID
    user_id: uuid.UUID
    language: Language
    status: ExecutionStatus
    stdout: str | None
    stderr: str | None
    exit_code: int | None
    duration_ms: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ExecutionSummary(BaseModel):
    """Lightweight shape for execution history listings — omits stdout/stderr."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_id: uuid.UUID
    language: Language
    status: ExecutionStatus
    exit_code: int | None
    duration_ms: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ExecutionWithProject(ExecutionSummary):
    project_name: str


class ExecutionStats(BaseModel):
    total: int
    successful: int
    failed: int
    last_activity_at: datetime | None
