import enum


class ProjectVisibility(str, enum.Enum):
    PRIVATE = "private"
    PUBLIC = "public"
