from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.bridge.models import (
    BridgeAdapterType,
    BridgeConversationListResponse,
    BridgeEventListResponse,
    BridgeEventStatus,
)
from ya_claw.controller.bridge import BridgeQueryController

router = APIRouter(prefix="/bridges", tags=["bridges"])
controller = BridgeQueryController()


@router.get("/conversations", response_model=BridgeConversationListResponse)
async def list_bridge_conversations(
    request: Request,
    adapter: BridgeAdapterType | None = None,
    tenant_key: str | None = None,
    external_chat_id: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
) -> BridgeConversationListResponse:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list_conversations(
            db_session,
            adapter=adapter,
            tenant_key=tenant_key,
            external_chat_id=external_chat_id,
            session_id=session_id,
            limit=limit,
        )


@router.get("/events", response_model=BridgeEventListResponse)
async def list_bridge_events(
    request: Request,
    adapter: BridgeAdapterType | None = None,
    tenant_key: str | None = None,
    conversation_id: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    external_chat_id: str | None = None,
    status: BridgeEventStatus | None = None,
    limit: int = 100,
) -> BridgeEventListResponse:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list_events(
            db_session,
            adapter=adapter,
            tenant_key=tenant_key,
            conversation_id=conversation_id,
            session_id=session_id,
            run_id=run_id,
            external_chat_id=external_chat_id,
            status=status,
            limit=limit,
        )


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    if not isinstance(session_factory, async_sessionmaker):
        raise HTTPException(status_code=503, detail="Database session factory is unavailable.")
    return session_factory
