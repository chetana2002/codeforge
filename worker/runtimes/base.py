from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeSpec:
    """Everything the sandbox needs to run one language's code: the base image,
    where the source file goes, how to invoke it, and the resource limits."""

    image: str
    filename: str
    command: list[str]
    timeout_seconds: int
    memory_limit_mb: int
    cpu_limit: float
    pids_limit: int
    working_dir: str = "/sandbox"
    env: dict[str, str] = field(default_factory=dict)
