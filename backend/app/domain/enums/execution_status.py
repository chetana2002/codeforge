import enum


class ExecutionStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# The execution state machine (see docs/execution-engine.md). Terminal states have
# no outgoing transitions.
ALLOWED_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.QUEUED: frozenset({ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED}),
    ExecutionStatus.RUNNING: frozenset(
        {
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.CANCELLED,
        }
    ),
    ExecutionStatus.SUCCESS: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.TIMEOUT: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.SUCCESS,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CANCELLED,
    }
)


def is_terminal(status: ExecutionStatus) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(from_status: ExecutionStatus, to_status: ExecutionStatus) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]


class InvalidExecutionTransitionError(Exception):
    def __init__(self, from_status: ExecutionStatus, to_status: ExecutionStatus):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Cannot transition execution from {from_status.value} to {to_status.value}"
        )


def ensure_transition(from_status: ExecutionStatus, to_status: ExecutionStatus) -> None:
    if not can_transition(from_status, to_status):
        raise InvalidExecutionTransitionError(from_status, to_status)
