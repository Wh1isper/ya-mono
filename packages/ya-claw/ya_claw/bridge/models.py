from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class BridgeAdapterType(StrEnum):
    LARK = "lark"


class BridgeDispatchMode(StrEnum):
    EMBEDDED = "embedded"
    MANUAL = "manual"


class BridgeEventStatus(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class BridgeInboundMessage(BaseModel):
    adapter: BridgeAdapterType
    tenant_key: str = "default"
    event_id: str
    message_id: str
    chat_id: str
    event_type: str = "im.message.receive_v1"
    sender_id: str | None = None
    sender_type: str | None = None
    chat_type: str | None = None
    message_type: str = "text"
    content_text: str | None = None
    content_json: dict[str, Any] | None = None
    create_time: str | None = None
    raw_event: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BridgeDispatchResult(BaseModel):
    status: BridgeEventStatus
    adapter: BridgeAdapterType
    event_id: str
    message_id: str | None = None
    chat_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    duplicate: bool = False
    error_message: str | None = None


class BridgeConversationSummary(BaseModel):
    id: str
    adapter: BridgeAdapterType
    tenant_key: str
    external_chat_id: str
    session_id: str
    project_id: str | None = None
    profile_name: str | None = None
    created_at: datetime
    updated_at: datetime
    last_event_at: datetime | None = None


class BridgeEventSummary(BaseModel):
    id: str
    adapter: BridgeAdapterType
    tenant_key: str
    event_id: str
    external_message_id: str | None = None
    external_chat_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    event_type: str
    status: BridgeEventStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
