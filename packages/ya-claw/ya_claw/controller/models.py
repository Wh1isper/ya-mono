from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, Field

from ya_claw.orm.tables import RunRecord, SessionRecord


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionStatus(StrEnum):
    IDLE = "idle"
    QUEUED = RunStatus.QUEUED
    RUNNING = RunStatus.RUNNING
    COMPLETED = RunStatus.COMPLETED
    FAILED = RunStatus.FAILED
    CANCELLED = RunStatus.CANCELLED


class TriggerType(StrEnum):
    API = "api"
    BRIDGE = "bridge"
    SCHEDULE = "schedule"
    HEARTBEAT = "heartbeat"


class TerminationReason(StrEnum):
    COMPLETED = "completed"
    ERROR = "error"
    CANCEL = "cancel"
    INTERRUPT = "interrupt"


class TextPart(BaseModel):
    type: Literal["text"]
    text: str
    metadata: dict[str, Any] | None = None


class UrlPart(BaseModel):
    type: Literal["url"]
    url: str
    kind: str
    filename: str | None = None
    storage: Literal["ephemeral", "persistent", "inline"] = "ephemeral"
    metadata: dict[str, Any] | None = None


class FilePart(BaseModel):
    type: Literal["file"]
    path: str
    kind: str
    metadata: dict[str, Any] | None = None


class BinaryPart(BaseModel):
    type: Literal["binary"]
    data: str
    mime_type: str
    kind: str
    filename: str | None = None
    storage: Literal["ephemeral", "persistent", "inline"] = "ephemeral"
    metadata: dict[str, Any] | None = None


class ModePart(BaseModel):
    type: Literal["mode"]
    mode: str
    params: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class CommandPart(BaseModel):
    type: Literal["command"]
    name: str
    params: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


InputPart = Annotated[
    ModePart | CommandPart | TextPart | UrlPart | FilePart | BinaryPart,
    Field(discriminator="type"),
]

ContentPart = Annotated[
    TextPart | UrlPart | FilePart | BinaryPart,
    Field(discriminator="type"),
]


class DispatchMode(StrEnum):
    QUEUE = "queue"
    ASYNC = "async"
    STREAM = "stream"


class UserInteraction(BaseModel):
    tool_call_id: str
    approved: bool
    reason: str | None = None
    user_input: Any | None = None


class ToolResult(BaseModel):
    tool_call_id: str
    content: Any
    error: str | None = None


class SessionCreateRequest(BaseModel):
    profile_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    input_parts: list[InputPart] = Field(default_factory=list)
    dispatch_mode: DispatchMode = DispatchMode.ASYNC
    trigger_type: TriggerType = TriggerType.API


class SessionRunCreateRequest(BaseModel):
    restore_from_run_id: str | None = None
    reset_state: bool = False
    input_parts: list[InputPart] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    dispatch_mode: DispatchMode = DispatchMode.ASYNC
    trigger_type: TriggerType = TriggerType.API


class SessionForkRequest(BaseModel):
    restore_from_run_id: str | None = None
    profile_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreateRequest(BaseModel):
    session_id: str | None = None
    restore_from_run_id: str | None = None
    reset_state: bool = False
    profile_name: str | None = None
    input_parts: list[InputPart] = Field(default_factory=list)
    trigger_type: TriggerType = TriggerType.API
    metadata: dict[str, Any] = Field(default_factory=dict)
    dispatch_mode: DispatchMode = DispatchMode.ASYNC


class SteerRequest(BaseModel):
    input_parts: list[InputPart] = Field(default_factory=list)


class RunSummary(BaseModel):
    id: str
    session_id: str
    sequence_no: int
    restore_from_run_id: str | None = None
    status: RunStatus
    trigger_type: TriggerType
    profile_name: str | None = None
    input_preview: str | None = None
    input_parts: list[InputPart] | None = None
    output_text: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    termination_reason: TerminationReason | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    committed_at: datetime | None = None
    message: list[dict[str, Any]] | None = None


class RunDetail(RunSummary):
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_state: bool = False
    has_message: bool = False


class SessionTurn(BaseModel):
    run_id: str
    session_id: str
    sequence_no: int
    restore_from_run_id: str | None = None
    profile_name: str | None = None
    input_preview: str | None = None
    input_parts: list[InputPart] = Field(default_factory=list)
    output_text: str | None = None
    output_summary: str | None = None
    created_at: datetime
    committed_at: datetime | None = None


class SessionTurnsResponse(BaseModel):
    session_id: str
    limit: int
    has_more: bool = False
    next_before_sequence_no: int | None = None
    turns: list[SessionTurn] = Field(default_factory=list)


class RunTraceItem(BaseModel):
    sequence_no: int
    type: Literal["tool_call", "tool_response"]
    tool_call_id: str | None = None
    tool_name: str | None = None
    message_id: str | None = None
    role: str | None = None
    content: str | None = None
    truncated: bool = False


class RunTraceResponse(BaseModel):
    run_id: str
    session_id: str
    item_count: int
    max_item_chars: int
    max_total_chars: int
    truncated: bool = False
    trace: list[RunTraceItem] = Field(default_factory=list)


class SessionSummary(BaseModel):
    id: str
    parent_session_id: str | None = None
    profile_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.IDLE
    run_count: int = 0
    head_run_id: str | None = None
    head_success_run_id: str | None = None
    active_run_id: str | None = None
    latest_run: RunSummary | None = None


class SessionDetail(SessionSummary):
    runs: list[RunSummary] = Field(default_factory=list)
    runs_limit: int = 0
    runs_has_more: bool = False
    runs_next_before_sequence_no: int | None = None


class SessionCreateResponse(BaseModel):
    session: SessionSummary
    run: RunDetail | None = None


class SessionGetResponse(BaseModel):
    session: SessionDetail
    state: dict[str, object] | None = None
    message: list[dict[str, Any]] | None = None


class RunGetResponse(BaseModel):
    session: SessionSummary
    run: RunDetail
    state: dict[str, object] | None = None
    message: list[dict[str, Any]] | None = None


class ControlResponse(BaseModel):
    session_id: str
    run_id: str
    status: RunStatus
    accepted: bool = True


class ProfileSubagent(BaseModel):
    name: str
    description: str
    system_prompt: str
    model: str | None = None
    model_settings_preset: str | None = None
    model_settings_override: dict[str, Any] | None = None
    model_config_preset: str | None = None
    model_config_override: dict[str, Any] | None = None


class ProfileMCPServer(BaseModel):
    transport: Literal["streamable_http"] = "streamable_http"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    required: bool = True


class ProfileUpsertRequest(BaseModel):
    model: str
    model_settings_preset: str | None = None
    model_settings_override: dict[str, Any] | None = None
    model_config_preset: str | None = None
    model_config_override: dict[str, Any] | None = None
    system_prompt: str | None = None
    builtin_toolsets: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("builtin_toolsets", "toolsets"),
    )
    subagents: list[ProfileSubagent] = Field(default_factory=list)
    include_builtin_subagents: bool = False
    unified_subagents: bool = False
    need_user_approve_tools: list[str] = Field(default_factory=list)
    need_user_approve_mcps: list[str] = Field(default_factory=list)
    enabled_mcps: list[str] = Field(default_factory=list)
    disabled_mcps: list[str] = Field(default_factory=list)
    mcp_servers: dict[str, ProfileMCPServer] = Field(default_factory=dict)
    workspace_backend_hint: str | None = None
    enabled: bool = True
    source_type: str | None = None
    source_version: str | None = None
    source_checksum: str | None = None


class ProfileSummary(BaseModel):
    name: str
    model: str
    workspace_backend_hint: str | None = None
    enabled: bool
    source_type: str | None = None
    source_version: str | None = None
    updated_at: datetime


class ProfileDetail(ProfileSummary):
    model_settings_preset: str | None = None
    model_settings_override: dict[str, Any] | None = None
    model_config_preset: str | None = None
    model_config_override: dict[str, Any] | None = None
    system_prompt: str | None = None
    builtin_toolsets: list[str] = Field(default_factory=list)
    toolsets: list[str] = Field(default_factory=list)
    subagents: list[ProfileSubagent] = Field(default_factory=list)
    include_builtin_subagents: bool = False
    unified_subagents: bool = False
    need_user_approve_tools: list[str] = Field(default_factory=list)
    need_user_approve_mcps: list[str] = Field(default_factory=list)
    enabled_mcps: list[str] = Field(default_factory=list)
    disabled_mcps: list[str] = Field(default_factory=list)
    mcp_servers: dict[str, ProfileMCPServer] = Field(default_factory=dict)
    source_checksum: str | None = None
    created_at: datetime


class ProfileSeedRequest(BaseModel):
    prune_missing: bool = False


class ProfileSeedResponse(BaseModel):
    seeded_names: list[str] = Field(default_factory=list)
    seed_file: str
    prune_missing: bool = False


def extract_input_preview(input_parts: list[InputPart]) -> str | None:
    for part in input_parts:
        if isinstance(part, TextPart):
            normalized_text = part.text.strip()
            if normalized_text:
                return normalized_text
    return None


def parse_input_parts(raw_input_parts: list[dict[str, Any]] | None) -> list[InputPart]:
    parsed_parts: list[InputPart] = []
    for raw_part in raw_input_parts or []:
        part_type = raw_part.get("type")
        if part_type == "text":
            parsed_parts.append(TextPart.model_validate(raw_part))
        elif part_type == "url":
            parsed_parts.append(UrlPart.model_validate(raw_part))
        elif part_type == "file":
            parsed_parts.append(FilePart.model_validate(raw_part))
        elif part_type == "binary":
            parsed_parts.append(BinaryPart.model_validate(raw_part))
        elif part_type == "mode":
            parsed_parts.append(ModePart.model_validate(raw_part))
        elif part_type == "command":
            parsed_parts.append(CommandPart.model_validate(raw_part))
        else:
            raise ValueError(f"Unsupported input part type: {part_type!r}")
    return parsed_parts


def public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return dict(metadata)


def parse_message_events(raw_message_payload: Any) -> list[dict[str, Any]] | None:
    if raw_message_payload is None:
        return None
    if not isinstance(raw_message_payload, list):
        raise TypeError("message payload must be a top-level JSON array of AGUI event objects")
    parsed_events = [event for event in raw_message_payload if isinstance(event, dict)]
    if len(parsed_events) != len(raw_message_payload):
        raise TypeError("message payload must contain only AGUI event objects")
    return parsed_events


def run_summary_from_record(
    record: RunRecord,
    *,
    message: list[dict[str, Any]] | None = None,
    include_input_parts: bool = False,
) -> RunSummary:
    input_parts = parse_input_parts(list(record.input_parts))
    termination_reason = TerminationReason(record.termination_reason) if record.termination_reason else None
    return RunSummary(
        id=record.id,
        session_id=record.session_id,
        sequence_no=record.sequence_no,
        restore_from_run_id=record.restore_from_run_id,
        status=RunStatus(record.status),
        trigger_type=TriggerType(record.trigger_type),
        profile_name=record.profile_name,
        input_preview=extract_input_preview(input_parts),
        input_parts=input_parts if include_input_parts else None,
        output_text=record.output_text,
        output_summary=record.output_summary,
        error_message=record.error_message,
        termination_reason=termination_reason,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        committed_at=record.committed_at,
        message=message,
    )


def run_detail_from_record(record: RunRecord, *, has_state: bool = False, has_message: bool = False) -> RunDetail:
    return RunDetail(
        **run_summary_from_record(record, include_input_parts=True).model_dump(),
        metadata=public_metadata(dict(record.run_metadata)),
        has_state=has_state,
        has_message=has_message,
    )


def session_turn_from_record(record: RunRecord) -> SessionTurn:
    input_parts = parse_input_parts(list(record.input_parts))
    return SessionTurn(
        run_id=record.id,
        session_id=record.session_id,
        sequence_no=record.sequence_no,
        restore_from_run_id=record.restore_from_run_id,
        profile_name=record.profile_name,
        input_preview=extract_input_preview(input_parts),
        input_parts=input_parts,
        output_text=record.output_text,
        output_summary=record.output_summary,
        created_at=record.created_at,
        committed_at=record.committed_at,
    )


def resolve_session_status(latest_run: RunSummary | None) -> SessionStatus:
    if latest_run is None:
        return SessionStatus.IDLE
    return SessionStatus(latest_run.status)


def session_summary_from_record(
    record: SessionRecord,
    *,
    run_count: int,
    latest_run: RunSummary | None,
) -> SessionSummary:
    return SessionSummary(
        id=record.id,
        parent_session_id=record.parent_session_id,
        profile_name=record.profile_name,
        metadata=public_metadata(dict(record.session_metadata)),
        created_at=record.created_at,
        updated_at=record.updated_at,
        status=resolve_session_status(latest_run),
        run_count=run_count,
        head_run_id=record.head_run_id,
        head_success_run_id=record.head_success_run_id,
        active_run_id=record.active_run_id,
        latest_run=latest_run,
    )
