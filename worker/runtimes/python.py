from config import WorkerSettings
from runtimes.base import RuntimeSpec


def python_runtime(settings: WorkerSettings) -> RuntimeSpec:
    return RuntimeSpec(
        image="python:3.12-slim",
        filename="main.py",
        command=["python", "main.py"],
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        cpu_limit=settings.execution_cpu_limit,
        pids_limit=settings.execution_pids_limit,
        env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
    )
