from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ya_claw.config import ClawSettings


def _parse_message_events(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Run message blob must be a top-level JSON array.")
    parsed_events = [event for event in payload if isinstance(event, dict)]
    if len(parsed_events) != len(payload):
        raise HTTPException(status_code=500, detail="Run message blob must contain only AGUI event objects.")
    return parsed_events


def _parse_state_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=500, detail="Run state blob must be a JSON object.")


def ensure_run_dir(settings: ClawSettings, run_id: str) -> Path:
    run_dir = settings.run_store_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_blob_path(settings: ClawSettings, run_id: str, blob_name: str) -> Path:
    return settings.run_store_dir / run_id / blob_name


def read_run_state_blob_if_exists(settings: ClawSettings, run_id: str) -> dict[str, Any] | None:
    blob_path = run_blob_path(settings, run_id, "state.json")
    if not blob_path.exists():
        return None
    return _parse_state_payload(load_json_blob(blob_path))


def read_run_message_blob_if_exists(settings: ClawSettings, run_id: str) -> list[dict[str, Any]] | None:
    blob_path = run_blob_path(settings, run_id, "message.json")
    if not blob_path.exists():
        return None
    return _parse_message_events(load_json_blob(blob_path))


def write_run_blob(settings: ClawSettings, run_id: str, blob_name: str, payload: Any) -> Path:
    run_dir = ensure_run_dir(settings, run_id)
    blob_path = run_dir / blob_name
    blob_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return blob_path


def load_json_blob(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
