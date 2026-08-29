"""Runs one execution inside a locked-down, ephemeral Docker container.

See docs/execution-engine.md and docs/security.md for the sandbox model.
Source code is passed in as a base64 env var and decoded by the container's
own entrypoint, rather than via put_archive() — Docker rejects put_archive
against any read_only container even when the target path is a tmpfs mount.
"""

import base64
import shlex
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, cast

import docker
from docker.errors import APIError, DockerException
from docker.models.containers import Container

from runtimes.base import RuntimeSpec

SandboxStatus = Literal["success", "failed", "timeout"]

_SOURCE_ENV_VAR = "CODEFORGE_SOURCE_B64"


@dataclass(frozen=True)
class SandboxResult:
    status: SandboxStatus
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int


def _wrapped_command(spec: RuntimeSpec) -> list[str]:
    target_path = f"{spec.working_dir.rstrip('/')}/{spec.filename}"
    real_command = shlex.join(spec.command)
    script = (
        f"printf '%s' \"${_SOURCE_ENV_VAR}\" | base64 -d > {shlex.quote(target_path)} && "
        f"exec {real_command}"
    )
    return ["sh", "-c", script]


class DockerSandboxRunner:
    def __init__(self, client: docker.DockerClient):
        self.client = client

    def run(self, spec: RuntimeSpec, code: str) -> SandboxResult:
        started = time.monotonic()
        encoded_source = base64.b64encode(code.encode("utf-8")).decode("ascii")
        env = {**spec.env, _SOURCE_ENV_VAR: encoded_source}

        container = self.client.containers.create(
            image=spec.image,
            command=_wrapped_command(spec),
            working_dir=spec.working_dir,
            environment=env,
            network_disabled=True,
            network_mode="none",
            mem_limit=f"{spec.memory_limit_mb}m",
            memswap_limit=f"{spec.memory_limit_mb}m",
            nano_cpus=int(spec.cpu_limit * 1_000_000_000),
            pids_limit=spec.pids_limit,
            user="1000:1000",
            read_only=True,
            # uid/gid must match user= below — tmpfs defaults to root:root.
            tmpfs={spec.working_dir: "rw,size=16m,exec,uid=1000,gid=1000,mode=0755"},
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            detach=True,
        )
        try:
            return self._run_created_container(container, spec, started)
        finally:
            with suppress(APIError, DockerException):
                container.remove(force=True)

    def _run_created_container(
        self, container: Container, spec: RuntimeSpec, started: float
    ) -> SandboxResult:
        container.start()

        timed_out = False
        exit_code: int | None = None
        try:
            wait_result = container.wait(timeout=spec.timeout_seconds)
            exit_code = wait_result.get("StatusCode")
        except Exception:
            # docker-py raises a generic requests exception on wait() timeout,
            # not a dedicated TimeoutError.
            timed_out = True
            with suppress(APIError, DockerException):
                container.kill()

        stdout = self._safe_logs(container, stdout=True, stderr=False)
        stderr = self._safe_logs(container, stdout=False, stderr=True)
        duration_ms = int((time.monotonic() - started) * 1000)

        if timed_out:
            status: SandboxStatus = "timeout"
        elif exit_code == 0:
            status = "success"
        else:
            status = "failed"

        return SandboxResult(
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _safe_logs(container: Container, *, stdout: bool, stderr: bool) -> str:
        try:
            raw = cast(bytes, container.logs(stdout=stdout, stderr=stderr))
            return raw.decode("utf-8", errors="replace")
        except (APIError, DockerException):
            return ""
