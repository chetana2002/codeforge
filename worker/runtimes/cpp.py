from config import WorkerSettings
from runtimes.base import RuntimeSpec


def cpp_runtime(settings: WorkerSettings) -> RuntimeSpec:
    return RuntimeSpec(
        image="gcc:13",
        filename="main.cpp",
        command=["sh", "-c", "g++ -O2 -o main main.cpp && ./main"],
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        cpu_limit=settings.execution_cpu_limit,
        pids_limit=settings.execution_pids_limit,
        env={"TMPDIR": "/sandbox"},
    )
