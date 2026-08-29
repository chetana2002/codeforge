from config import get_worker_settings


def test_worker_settings_load_with_defaults() -> None:
    settings = get_worker_settings()
    assert settings.stream_key == "codeforge:executions"
    assert settings.execution_timeout_seconds > 0
