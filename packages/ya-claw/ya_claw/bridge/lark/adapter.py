from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any

from ya_claw.bridge.base import BridgeAdapter, BridgeMessageHandler
from ya_claw.bridge.lark.normalizer import normalize_lark_event
from ya_claw.bridge.models import BridgeAdapterType
from ya_claw.config import ClawSettings

logger = logging.getLogger(__name__)


class LarkBridgeAdapter(BridgeAdapter):
    def __init__(self, *, settings: ClawSettings, handler: BridgeMessageHandler) -> None:
        self._settings = settings
        self._handler = handler
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any | None = None
        self._stopping = False
        self._pending_submissions: set[Future[object]] = set()

    @property
    def adapter_type(self) -> BridgeAdapterType:
        return BridgeAdapterType.LARK

    async def run(self) -> None:
        app_id = self._settings.bridge_lark_app_id
        app_secret = self._settings.bridge_lark_app_secret_value
        if app_id is None or app_id.strip() == "" or app_secret is None:
            raise RuntimeError("Lark bridge requires YA_CLAW_BRIDGE_LARK_APP_ID and YA_CLAW_BRIDGE_LARK_APP_SECRET.")
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        try:
            await asyncio.to_thread(self._run_websocket_client, app_id.strip(), app_secret)
        finally:
            self._client = None
            self._loop = None

    async def stop(self) -> None:
        self._stopping = True
        for future in list(self._pending_submissions):
            future.cancel()
        self._pending_submissions.clear()
        await asyncio.to_thread(_stop_lark_ws_loop)

    def _run_websocket_client(self, app_id: str, app_secret: str) -> None:
        import lark_oapi as lark
        from lark_oapi.ws import Client

        def handle_event(data: object) -> None:
            raw_event = _marshal_lark_payload(lark, data)
            message = normalize_lark_event(raw_event)
            if message is None:
                return
            self._submit_from_sdk_thread(self._handler.handle_message(message))

        event_handler_builder = lark.EventDispatcherHandler.builder("", "", lark.LogLevel.INFO)
        for event_type in self._settings.resolved_bridge_lark_event_types:
            event_handler_builder.register_p2_customized_event(event_type, handle_event)
        event_handler = event_handler_builder.build()
        client = Client(
            app_id=app_id,
            app_secret=app_secret,
            log_level=lark.LogLevel.INFO,
            event_handler=event_handler,
            domain=self._settings.bridge_lark_domain,
            auto_reconnect=True,
        )
        self._client = client
        with contextlib.suppress(RuntimeError):
            client.start()

    def _submit_from_sdk_thread(self, coroutine: Coroutine[Any, Any, object]) -> None:
        if self._stopping:
            coroutine.close()
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            coroutine.close()
            logger.warning("Dropping Lark bridge message because the runtime loop is unavailable.")
            return
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        self._pending_submissions.add(future)
        future.add_done_callback(self._complete_submission)

    def _complete_submission(self, future: Future[object]) -> None:
        self._pending_submissions.discard(future)
        if future.cancelled():
            return
        try:
            future.result()
        except Exception:
            logger.exception("Lark bridge message handler failed.")


def _marshal_lark_payload(lark_module: Any, payload: Any) -> dict[str, Any]:
    raw_json = lark_module.JSON.marshal(payload)
    parsed = lark_module.JSON.unmarshal(raw_json, dict)
    return parsed if isinstance(parsed, dict) else {}


def _stop_lark_ws_loop() -> None:
    with contextlib.suppress(Exception):
        import lark_oapi.ws.client as lark_ws_client

        lark_ws_client.loop.call_soon_threadsafe(lark_ws_client.loop.stop)
