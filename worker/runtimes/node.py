from config import WorkerSettings
from runtimes.base import RuntimeSpec


def node_runtime(settings: WorkerSettings) -> RuntimeSpec:
    return RuntimeSpec(
        image="node:22-alpine",
        filename="main.js",
        command=["node", "main.js"],
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        cpu_limit=settings.execution_cpu_limit,
        pids_limit=settings.execution_pids_limit,
    )
