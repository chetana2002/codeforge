from config import WorkerSettings
from runtimes.base import RuntimeSpec


def java_runtime(settings: WorkerSettings) -> RuntimeSpec:
    return RuntimeSpec(
        image="eclipse-temurin:21-jdk-alpine",
        filename="Main.java",
        # -XX:-UsePerfData: the JVM otherwise memory-maps a file under
        # /tmp/hsperfdata_* on startup, which fails on this container's
        # read-only root (only working_dir is writable).
        command=["sh", "-c", "javac Main.java && java -XX:-UsePerfData Main"],
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        cpu_limit=settings.execution_cpu_limit,
        pids_limit=settings.execution_pids_limit,
        env={"TMPDIR": "/sandbox"},
    )
