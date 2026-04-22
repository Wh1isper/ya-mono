from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ya_claw.execution.store import RunStore


@dataclass(slots=True)
class MessageCheckpoint:
    run_id: str
    session_id: str
    checkpoint_kind: str
    message: list[dict[str, Any]]
    created_at: datetime

    def model_dump(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "checkpoint_kind": self.checkpoint_kind,
            "created_at": self.created_at.isoformat(),
            "message": list(self.message),
        }


def build_message_checkpoint(
    *,
    run_id: str,
    session_id: str,
    checkpoint_kind: str,
    message: list[dict[str, Any]],
    created_at: datetime | None = None,
) -> MessageCheckpoint:
    return MessageCheckpoint(
        run_id=run_id,
        session_id=session_id,
        checkpoint_kind=checkpoint_kind,
        message=list(message),
        created_at=created_at or datetime.now(UTC),
    )


def write_message_checkpoint(run_store: RunStore, checkpoint: MessageCheckpoint) -> None:
    run_store.write_checkpoint_message(
        checkpoint.run_id,
        list(checkpoint.message),
        checkpoint_kind=checkpoint.checkpoint_kind,
    )


def commit_run_artifacts(
    run_store: RunStore,
    *,
    run_id: str,
    session_id: str,
    state: dict[str, Any],
    message: list[dict[str, Any]],
    committed_at: datetime | None = None,
) -> None:
    effective_committed_at = committed_at or datetime.now(UTC)
    run_store.write_state(
        run_id,
        {
            **state,
            "run_id": run_id,
            "session_id": session_id,
            "committed_at": effective_committed_at.isoformat(),
        },
    )
    run_store.write_message(run_id, list(message))
