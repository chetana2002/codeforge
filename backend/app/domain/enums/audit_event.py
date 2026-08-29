import enum


class AuditEventType(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    PROJECT_CREATED = "project_created"
    PROJECT_DELETED = "project_deleted"
    FILE_CREATED = "file_created"
    FILE_DELETED = "file_deleted"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_CANCELLED = "execution_cancelled"
