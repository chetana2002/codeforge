import pytest

from config import get_worker_settings
from runtimes.node import node_runtime
from runtimes.python import python_runtime
from runtimes.registry import UnsupportedLanguageError, get_runtime


def test_python_runtime_spec() -> None:
    settings = get_worker_settings()
    spec = python_runtime(settings)
    assert spec.image == "python:3.12-slim"
    assert spec.filename == "main.py"
    assert spec.command == ["python", "main.py"]
    assert spec.timeout_seconds == settings.execution_timeout_seconds


def test_node_runtime_spec() -> None:
    settings = get_worker_settings()
    spec = node_runtime(settings)
    assert spec.image == "node:22-alpine"
    assert spec.filename == "main.js"
    assert spec.command == ["node", "main.js"]


def test_get_runtime_python() -> None:
    settings = get_worker_settings()
    spec = get_runtime("python", settings)
    assert spec.filename == "main.py"


def test_get_runtime_javascript() -> None:
    settings = get_worker_settings()
    spec = get_runtime("javascript", settings)
    assert spec.filename == "main.js"


def test_get_runtime_unsupported_language_raises() -> None:
    settings = get_worker_settings()
    with pytest.raises(UnsupportedLanguageError):
        get_runtime("rust", settings)
