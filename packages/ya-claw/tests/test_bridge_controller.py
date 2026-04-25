from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from ya_claw.bridge.controller import BridgeController
from ya_claw.bridge.models import BridgeAdapterType, BridgeEventStatus, BridgeInboundMessage
from ya_claw.config import ClawSettings
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.orm.base import Base
from ya_claw.orm.tables import BridgeConversationRecord, BridgeEventRecord, RunRecord
from ya_claw.runtime_state import create_runtime_state


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncEngine:
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'bridge.sqlite3').resolve()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    session_factory = create_session_factory(db_engine)
    async with session_factory() as session:
        yield session


async def test_bridge_controller_maps_chat_to_session_and_dedupes(db_session: AsyncSession) -> None:
    runtime_state = create_runtime_state()
    controller = BridgeController()
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        bridge_lark_default_profile="default",
        _env_file=None,
    )
    message = BridgeInboundMessage(
        adapter=BridgeAdapterType.LARK,
        tenant_key="tenant-1",
        event_id="event-1",
        message_id="om_1",
        chat_id="oc_1",
        sender_id="ou_1",
        content_text="hello",
    )

    result = await controller.handle_inbound_message(
        db_session,
        settings,
        runtime_state,
        RunDispatcher(None),
        message,
    )

    assert result.status == BridgeEventStatus.QUEUED
    assert result.session_id is not None
    assert result.run_id is not None
    conversation_result = await db_session.execute(
        select(BridgeConversationRecord).where(
            BridgeConversationRecord.adapter == BridgeAdapterType.LARK,
            BridgeConversationRecord.tenant_key == "tenant-1",
            BridgeConversationRecord.external_chat_id == "oc_1",
        )
    )
    conversation = conversation_result.scalar_one()
    assert conversation.session_id == result.session_id

    event_result = await db_session.execute(
        select(BridgeEventRecord).where(
            BridgeEventRecord.adapter == BridgeAdapterType.LARK,
            BridgeEventRecord.tenant_key == "tenant-1",
            BridgeEventRecord.event_id == "event-1",
        )
    )
    event_record = event_result.scalar_one()
    assert event_record.status == BridgeEventStatus.QUEUED
    assert event_record.conversation_id == conversation.id
    assert event_record.session_id == result.session_id
    assert event_record.run_id == result.run_id

    duplicate = await controller.handle_inbound_message(
        db_session,
        settings,
        runtime_state,
        RunDispatcher(None),
        message,
    )

    assert duplicate.status == BridgeEventStatus.DUPLICATE
    assert duplicate.duplicate is True
    assert duplicate.session_id == result.session_id
    assert duplicate.run_id == result.run_id


async def test_bridge_controller_reuses_chat_session(db_session: AsyncSession) -> None:
    runtime_state = create_runtime_state()
    controller = BridgeController()
    settings = ClawSettings(api_token="test-token", _env_file=None)  # noqa: S106

    first = await controller.handle_inbound_message(
        db_session,
        settings,
        runtime_state,
        RunDispatcher(None),
        BridgeInboundMessage(
            adapter=BridgeAdapterType.LARK,
            tenant_key="tenant-1",
            event_id="event-1",
            message_id="om_1",
            chat_id="oc_1",
            content_text="first",
        ),
    )
    second = await controller.handle_inbound_message(
        db_session,
        settings,
        runtime_state,
        RunDispatcher(None),
        BridgeInboundMessage(
            adapter=BridgeAdapterType.LARK,
            tenant_key="tenant-1",
            event_id="event-2",
            message_id="om_2",
            chat_id="oc_1",
            content_text="second",
        ),
    )

    assert first.session_id == second.session_id
    assert first.run_id != second.run_id
    assert second.run_id is not None
    run_record = await db_session.get(RunRecord, second.run_id)
    assert isinstance(run_record, RunRecord)
    assert run_record.trigger_type == "bridge"
