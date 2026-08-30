from config import WorkerSettings
from runtimes.base import RuntimeSpec


def c_runtime(settings: WorkerSettings) -> RuntimeSpec:
    return RuntimeSpec(
        image="gcc:13",
        filename="main.c",
        command=["sh", "-c", "gcc -O2 -o main main.c && ./main"],
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        cpu_limit=settings.execution_cpu_limit,
        pids_limit=settings.execution_pids_limit,
        # gcc writes intermediate object files to TMPDIR; the container's only
        # writable path is the working_dir tmpfs.
        env={"TMPDIR": "/sandbox"},
    )
