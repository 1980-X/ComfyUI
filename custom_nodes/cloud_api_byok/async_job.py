import time
from collections.abc import Callable
from typing import Any


def poll_until(
    fetch_status: Callable[[], tuple[str, Any]],
    *,
    interval_sec: float = 3.0,
    timeout_sec: float = 600.0,
    success_states: set[str] | None = None,
    failure_states: set[str] | None = None,
) -> Any:
    """Poll until success/failure. fetch_status returns (state, payload)."""
    success_states = success_states or {"SUCCEEDED", "SUCCESS", "success", "5", "COMPLETED"}
    failure_states = failure_states or {"FAILED", "FAILURE", "failed", "4", "CANCELED", "CANCELLED"}
    deadline = time.time() + timeout_sec
    last_state = ""
    last_payload: Any = None
    while time.time() < deadline:
        state, payload = fetch_status()
        last_state, last_payload = str(state), payload
        if last_state in success_states:
            return payload
        if last_state in failure_states:
            raise RuntimeError(f"异步任务失败 state={last_state}: {payload}")
        time.sleep(interval_sec)
    raise RuntimeError(f"异步任务超时 state={last_state}: {last_payload}")
