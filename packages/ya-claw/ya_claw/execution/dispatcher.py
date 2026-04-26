from __future__ import annotations

from loguru import logger
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
        logger.debug("Dispatching run run_id={} mode={}", run_id, mode)
        if mode == DispatchMode.QUEUE:
            logger.info("Run kept queued run_id={} mode={} reason=queued_only", run_id, mode)
            return RunDispatchResult(run_id=run_id, mode=mode, submitted=False, reason="queued_only")
        if self._supervisor is None:
            logger.warning("Run dispatch skipped run_id={} mode={} reason=supervisor_unavailable", run_id, mode)
            return RunDispatchResult(run_id=run_id, mode=mode, submitted=False, reason="supervisor_unavailable")
        submitted = self._supervisor.submit_run(run_id)
        reason = None if submitted else self._skipped_reason(run_id)
        logger.info(
            "Run dispatch result run_id={} mode={} submitted={} reason={}",
            run_id,
            mode,
            submitted,
            reason,
        )
        return RunDispatchResult(
            run_id=run_id,
            mode=mode,
            submitted=submitted,
            reason=reason,
        )

    def _skipped_reason(self, run_id: str) -> str:
        supervisor = self._supervisor
        if supervisor is None:
            return "supervisor_unavailable"
        if not supervisor.accepting_submissions:
            return "supervisor_shutting_down"
        if supervisor.get_background_task(run_id) is not None:
            return "already_submitted"
        return "submission_skipped"
