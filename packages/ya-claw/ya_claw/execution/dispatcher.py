from __future__ import annotations

from pydantic import BaseModel

from ya_claw.controller.models import DispatchMode
from ya_claw.execution.coordinator import ExecutionSupervisor


class RunDispatchResult(BaseModel):
    run_id: str
    mode: DispatchMode
    submitted: bool = False
    reason: str | None = None


class RunDispatcher:
    def __init__(self, supervisor: ExecutionSupervisor | None) -> None:
        self._supervisor = supervisor

    def dispatch(self, run_id: str, mode: DispatchMode) -> RunDispatchResult:
        if mode == DispatchMode.QUEUE:
            return RunDispatchResult(run_id=run_id, mode=mode, submitted=False, reason="queued_only")
        if self._supervisor is None:
            return RunDispatchResult(run_id=run_id, mode=mode, submitted=False, reason="supervisor_unavailable")
        if not self._supervisor.execution_enabled:
            return RunDispatchResult(run_id=run_id, mode=mode, submitted=False, reason="execution_model_unconfigured")
        submitted = self._supervisor.submit_run(run_id)
        return RunDispatchResult(
            run_id=run_id,
            mode=mode,
            submitted=submitted,
            reason=None if submitted else "already_submitted",
        )
