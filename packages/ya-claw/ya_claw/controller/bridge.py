from __future__ import annotations

from typing import cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.bridge.models import (
    BridgeAdapterType,
    BridgeConversationListResponse,
    BridgeConversationSummary,
    BridgeEventListResponse,
    BridgeEventStatus,
    BridgeEventSummary,
)
from ya_claw.orm.tables import BridgeConversationRecord, BridgeEventRecord, RunRecord, SessionRecord


class BridgeQueryController:
    async def list_conversations(
        self,
        db_session: AsyncSession,
        *,
        adapter: BridgeAdapterType | None = None,
        tenant_key: str | None = None,
        external_chat_id: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> BridgeConversationListResponse:
        normalized_limit = min(max(limit, 1), 500)
        statement: Select[tuple[BridgeConversationRecord, str | None]] = (
            select(BridgeConversationRecord, SessionRecord.active_run_id)
            .outerjoin(SessionRecord, BridgeConversationRecord.session_id == SessionRecord.id)
            .order_by(BridgeConversationRecord.last_event_at.desc(), BridgeConversationRecord.updated_at.desc())
            .limit(normalized_limit)
        )
        if adapter is not None:
            statement = statement.where(BridgeConversationRecord.adapter == adapter)
        if isinstance(tenant_key, str) and tenant_key.strip() != "":
            statement = statement.where(BridgeConversationRecord.tenant_key == tenant_key.strip())
        if isinstance(external_chat_id, str) and external_chat_id.strip() != "":
            statement = statement.where(BridgeConversationRecord.external_chat_id == external_chat_id.strip())
        if isinstance(session_id, str) and session_id.strip() != "":
            statement = statement.where(BridgeConversationRecord.session_id == session_id.strip())

        result = await db_session.execute(statement)
        rows = result.all()
        summaries = [
            await self._conversation_summary_from_record(db_session, record, active_run_id=active_run_id)
            for record, active_run_id in rows
            if isinstance(record, BridgeConversationRecord)
        ]
        return BridgeConversationListResponse(conversations=summaries)

    async def list_events(
        self,
        db_session: AsyncSession,
        *,
        adapter: BridgeAdapterType | None = None,
        tenant_key: str | None = None,
        conversation_id: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        external_chat_id: str | None = None,
        status: BridgeEventStatus | None = None,
        limit: int = 100,
    ) -> BridgeEventListResponse:
        normalized_limit = min(max(limit, 1), 500)
        statement: Select[tuple[BridgeEventRecord, str]] = (
            select(BridgeEventRecord, RunRecord.status)
            .outerjoin(RunRecord, BridgeEventRecord.run_id == RunRecord.id)
            .order_by(BridgeEventRecord.created_at.desc())
            .limit(normalized_limit)
        )
        if adapter is not None:
            statement = statement.where(BridgeEventRecord.adapter == adapter)
        if isinstance(tenant_key, str) and tenant_key.strip() != "":
            statement = statement.where(BridgeEventRecord.tenant_key == tenant_key.strip())
        if isinstance(conversation_id, str) and conversation_id.strip() != "":
            statement = statement.where(BridgeEventRecord.conversation_id == conversation_id.strip())
        if isinstance(session_id, str) and session_id.strip() != "":
            statement = statement.where(BridgeEventRecord.session_id == session_id.strip())
        if isinstance(run_id, str) and run_id.strip() != "":
            statement = statement.where(BridgeEventRecord.run_id == run_id.strip())
        if isinstance(external_chat_id, str) and external_chat_id.strip() != "":
            statement = statement.where(BridgeEventRecord.external_chat_id == external_chat_id.strip())
        if status is not None:
            statement = statement.where(BridgeEventRecord.status == status)

        result = await db_session.execute(statement)
        return BridgeEventListResponse(
            events=[
                event_summary_from_record(record, run_status=run_status)
                for record, run_status in result.all()
                if isinstance(record, BridgeEventRecord)
            ]
        )

    async def _conversation_summary_from_record(
        self,
        db_session: AsyncSession,
        record: BridgeConversationRecord,
        *,
        active_run_id: str | None,
    ) -> BridgeConversationSummary:
        event_count_result = await db_session.execute(
            select(func.count()).select_from(BridgeEventRecord).where(BridgeEventRecord.conversation_id == record.id)
        )
        event_count = cast(int, event_count_result.scalar_one())
        latest_event_result = await db_session.execute(
            select(BridgeEventRecord)
            .where(BridgeEventRecord.conversation_id == record.id)
            .order_by(BridgeEventRecord.created_at.desc())
            .limit(1)
        )
        latest_event = latest_event_result.scalar_one_or_none()
        latest_event_status = (
            BridgeEventStatus(latest_event.status) if isinstance(latest_event, BridgeEventRecord) else None
        )
        return BridgeConversationSummary(
            id=record.id,
            adapter=BridgeAdapterType(record.adapter),
            tenant_key=record.tenant_key,
            external_chat_id=record.external_chat_id,
            session_id=record.session_id,
            profile_name=record.profile_name,
            metadata=record.conversation_metadata,
            active_run_id=active_run_id,
            event_count=event_count,
            latest_event_status=latest_event_status,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_event_at=record.last_event_at,
        )


def event_summary_from_record(record: BridgeEventRecord, *, run_status: str | None = None) -> BridgeEventSummary:
    return BridgeEventSummary(
        id=record.id,
        adapter=BridgeAdapterType(record.adapter),
        tenant_key=record.tenant_key,
        event_id=record.event_id,
        external_message_id=record.external_message_id,
        external_chat_id=record.external_chat_id,
        conversation_id=record.conversation_id,
        session_id=record.session_id,
        run_id=record.run_id,
        run_status=run_status,
        event_type=record.event_type,
        status=BridgeEventStatus(record.status),
        error_message=record.error_message,
        raw_event=record.raw_event,
        normalized_event=record.normalized_event,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
