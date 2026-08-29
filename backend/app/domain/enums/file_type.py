import enum


class FileType(str, enum.Enum):
    FILE = "file"
    FOLDER = "folder"
