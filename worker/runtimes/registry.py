from collections.abc import Callable

from config import WorkerSettings
from runtimes.base import RuntimeSpec
from runtimes.c import c_runtime
from runtimes.cpp import cpp_runtime
from runtimes.java import java_runtime
from runtimes.node import node_runtime
from runtimes.python import python_runtime

_REGISTRY: dict[str, Callable[[WorkerSettings], RuntimeSpec]] = {
    "python": python_runtime,
    "javascript": node_runtime,
    "c": c_runtime,
    "cpp": cpp_runtime,
    "java": java_runtime,
}


class UnsupportedLanguageError(Exception):
    def __init__(self, language: str):
        self.language = language
        super().__init__(f"No execution runtime registered for language: {language}")


def get_runtime(language: str, settings: WorkerSettings) -> RuntimeSpec:
    factory = _REGISTRY.get(language)
    if factory is None:
        raise UnsupportedLanguageError(language)
    return factory(settings)
