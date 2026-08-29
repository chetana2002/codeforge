"""Integration tests that actually run containers via the local Docker daemon —
these exercise the real sandbox security guarantees (no network, timeouts,
process limits), not mocks of them. Requires Docker to be running locally.
"""

import docker
import pytest

from runtimes.base import RuntimeSpec
from sandbox.docker_runner import DockerSandboxRunner


@pytest.fixture(scope="module")
def docker_client() -> docker.DockerClient:
    client = docker.from_env()
    client.ping()
    return client


@pytest.fixture(scope="module")
def runner(docker_client: docker.DockerClient) -> DockerSandboxRunner:
    return DockerSandboxRunner(docker_client)


def _python_spec(**overrides: object) -> RuntimeSpec:
    defaults: dict[str, object] = {
        "image": "python:3.12-slim",
        "filename": "main.py",
        "command": ["python", "main.py"],
        "timeout_seconds": 10,
        "memory_limit_mb": 128,
        "cpu_limit": 0.5,
        "pids_limit": 32,
    }
    defaults.update(overrides)
    return RuntimeSpec(**defaults)  # type: ignore[arg-type]


@pytest.mark.timeout(60)
def test_successful_execution_captures_stdout(runner: DockerSandboxRunner) -> None:
    result = runner.run(_python_spec(), 'print("Hello from CodeForge!")')
    assert result.status == "success"
    assert result.exit_code == 0
    assert "Hello from CodeForge!" in result.stdout
    assert result.duration_ms >= 0


@pytest.mark.timeout(60)
def test_failing_code_captures_stderr(runner: DockerSandboxRunner) -> None:
    result = runner.run(_python_spec(), 'raise ValueError("boom")')
    assert result.status == "failed"
    assert result.exit_code == 1
    assert "ValueError" in result.stderr
    assert "boom" in result.stderr


@pytest.mark.timeout(60)
def test_infinite_loop_times_out(runner: DockerSandboxRunner) -> None:
    result = runner.run(_python_spec(timeout_seconds=2), "while True:\n    pass\n")
    assert result.status == "timeout"
    assert result.exit_code is None


@pytest.mark.timeout(60)
def test_network_access_is_disabled(runner: DockerSandboxRunner) -> None:
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('8.8.8.8', 53), timeout=3)\n"
        "    print('NETWORK_REACHABLE')\n"
        "except OSError:\n"
        "    print('NETWORK_BLOCKED')\n"
    )
    result = runner.run(_python_spec(timeout_seconds=8), code)
    assert "NETWORK_BLOCKED" in result.stdout
    assert "NETWORK_REACHABLE" not in result.stdout


@pytest.mark.timeout(60)
def test_process_limit_prevents_fork_bomb(runner: DockerSandboxRunner) -> None:
    code = (
        "import os\n"
        "import time\n"
        "spawned = 0\n"
        "try:\n"
        "    for _ in range(200):\n"
        "        os.fork()\n"
        "        spawned += 1\n"
        "except BlockingIOError:\n"
        "    pass\n"
        "except OSError:\n"
        "    pass\n"
        "time.sleep(0.5)\n"
        "print(f'SPAWNED={spawned}')\n"
    )
    result = runner.run(_python_spec(timeout_seconds=8, pids_limit=16), code)
    # The pids_limit cgroup must have stopped the fork loop well short of 200 —
    # the exact count is nondeterministic (scheduler-dependent), so we only
    # assert it was actually constrained rather than pinning a specific number.
    assert "SPAWNED=200" not in result.stdout


@pytest.mark.timeout(60)
def test_filesystem_is_read_only_outside_working_dir(runner: DockerSandboxRunner) -> None:
    code = (
        "try:\n"
        "    open('/etc/CODEFORGE_TEST_WRITE', 'w').close()\n"
        "    print('WRITE_SUCCEEDED')\n"
        "except OSError:\n"
        "    print('WRITE_BLOCKED')\n"
    )
    result = runner.run(_python_spec(), code)
    assert "WRITE_BLOCKED" in result.stdout


@pytest.mark.timeout(60)
def test_container_is_removed_after_run(
    docker_client: docker.DockerClient, runner: DockerSandboxRunner
) -> None:
    before = {c.id for c in docker_client.containers.list(all=True)}
    runner.run(_python_spec(), 'print("cleanup check")')
    after = {c.id for c in docker_client.containers.list(all=True)}
    assert after - before == set()
