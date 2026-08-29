"""Runs one execution inside a locked-down, ephemeral Docker container.

Security model (see docs/security.md and docs/execution-engine.md): no network access,
CPU/memory/PID limits, non-root user, read-only root filesystem with a small
tmpfs scratch dir for the working directory, no extra Linux capabilities, and
automatic container removal after every run — success, failure, or timeout.

Getting code into a read-only-rootfs container: the Docker Engine API's
put_archive() call — the usual way to inject files without a host bind mount —
unconditionally rejects writes against any container whose HostConfig has
ReadonlyRootfs set, regardless of whether the target path has its own tmpfs
mount (confirmed empirically: 400 "container rootfs is marked read-only", even
against a path covered by `tmpfs=`, even after the container has started and
that tmpfs is genuinely mounted and writable from *inside* the container).
Rather than drop read_only to work around that, the source is instead passed
in as a base64-encoded environment variable, and the container's own entrypoint
decodes it into the tmpfs-mounted working directory before exec'ing the real
run command — a plain shell redirect, which the read-only check doesn't apply
to since it never goes through the Engine API's write path at all.

This also avoids a Docker-outside-of-Docker bind-mount trap: the worker itself
runs inside its own container and talks to the *host's* Docker daemon over the
mounted socket, so any path the worker writes to on its own filesystem is
meaningless to the daemon — only paths that exist on the host resolve for a
bind mount. An env var has no such path-namespace mismatch.
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
            # uid/gid must match the non-root `user=` below — a tmpfs mount
            # defaults to root:root ownership, which the sandboxed process
            # (running as uid 1000) would otherwise have no write access to.
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
            # docker-py surfaces a blocking-read timeout as a requests/urllib3
            # exception, not a dedicated TimeoutError — any failure to observe
            # completion within the deadline is treated as a timeout, and the
            # container is force-killed regardless of what actually happened.
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
