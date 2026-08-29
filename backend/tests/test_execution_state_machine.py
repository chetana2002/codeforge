import pytest

from app.domain.enums.execution_status import (
    ExecutionStatus,
    InvalidExecutionTransitionError,
    can_transition,
    ensure_transition,
    is_terminal,
)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ExecutionStatus.QUEUED, ExecutionStatus.RUNNING),
        (ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED),
        (ExecutionStatus.RUNNING, ExecutionStatus.SUCCESS),
        (ExecutionStatus.RUNNING, ExecutionStatus.FAILED),
        (ExecutionStatus.RUNNING, ExecutionStatus.TIMEOUT),
        (ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED),
    ],
)
def test_allowed_transitions(from_status: ExecutionStatus, to_status: ExecutionStatus) -> None:
    assert can_transition(from_status, to_status)
    ensure_transition(from_status, to_status)  # must not raise


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ExecutionStatus.QUEUED, ExecutionStatus.SUCCESS),
        (ExecutionStatus.QUEUED, ExecutionStatus.FAILED),
        (ExecutionStatus.QUEUED, ExecutionStatus.TIMEOUT),
        (ExecutionStatus.RUNNING, ExecutionStatus.QUEUED),
        (ExecutionStatus.SUCCESS, ExecutionStatus.RUNNING),
        (ExecutionStatus.FAILED, ExecutionStatus.RUNNING),
        (ExecutionStatus.TIMEOUT, ExecutionStatus.RUNNING),
        (ExecutionStatus.CANCELLED, ExecutionStatus.RUNNING),
        (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED),
        (ExecutionStatus.CANCELLED, ExecutionStatus.SUCCESS),
    ],
)
def test_invalid_transitions_rejected(
    from_status: ExecutionStatus, to_status: ExecutionStatus
) -> None:
    assert not can_transition(from_status, to_status)
    with pytest.raises(InvalidExecutionTransitionError):
        ensure_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ExecutionStatus.QUEUED, False),
        (ExecutionStatus.RUNNING, False),
        (ExecutionStatus.SUCCESS, True),
        (ExecutionStatus.FAILED, True),
        (ExecutionStatus.TIMEOUT, True),
        (ExecutionStatus.CANCELLED, True),
    ],
)
def test_is_terminal(status: ExecutionStatus, expected: bool) -> None:
    assert is_terminal(status) is expected


def test_every_status_has_a_transition_table_entry() -> None:
    from app.domain.enums.execution_status import ALLOWED_TRANSITIONS

    assert set(ALLOWED_TRANSITIONS.keys()) == set(ExecutionStatus)
