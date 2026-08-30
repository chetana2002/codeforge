import enum


class Language(str, enum.Enum):
    """Languages a project can be configured for. The execution worker maps each
    value to a concrete ExecutionRuntime (see worker/runtimes/)."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    C = "c"
    CPP = "cpp"
    JAVA = "java"
