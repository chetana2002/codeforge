import pytest

from config import get_worker_settings
from runtimes.c import c_runtime
from runtimes.cpp import cpp_runtime
from runtimes.java import java_runtime
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


def test_c_runtime_spec() -> None:
    settings = get_worker_settings()
    spec = c_runtime(settings)
    assert spec.image == "gcc:13"
    assert spec.filename == "main.c"
    assert spec.command == ["sh", "-c", "gcc -O2 -o main main.c && ./main"]


def test_cpp_runtime_spec() -> None:
    settings = get_worker_settings()
    spec = cpp_runtime(settings)
    assert spec.image == "gcc:13"
    assert spec.filename == "main.cpp"
    assert spec.command == ["sh", "-c", "g++ -O2 -o main main.cpp && ./main"]


def test_java_runtime_spec() -> None:
    settings = get_worker_settings()
    spec = java_runtime(settings)
    assert spec.image == "eclipse-temurin:21-jdk-alpine"
    assert spec.filename == "Main.java"
    assert spec.command == ["sh", "-c", "javac Main.java && java -XX:-UsePerfData Main"]


def test_get_runtime_c() -> None:
    settings = get_worker_settings()
    spec = get_runtime("c", settings)
    assert spec.filename == "main.c"


def test_get_runtime_cpp() -> None:
    settings = get_worker_settings()
    spec = get_runtime("cpp", settings)
    assert spec.filename == "main.cpp"


def test_get_runtime_java() -> None:
    settings = get_worker_settings()
    spec = get_runtime("java", settings)
    assert spec.filename == "Main.java"


def test_get_runtime_unsupported_language_raises() -> None:
    settings = get_worker_settings()
    with pytest.raises(UnsupportedLanguageError):
        get_runtime("rust", settings)
